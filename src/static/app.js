// Interfaz de Nafteando: arma el pedido, muestra la respuesta y el mapa.
// Toda la cuenta la hace el servidor (src/recomendador.py).

const formulario = document.getElementById("formulario");
const resultado = document.getElementById("resultado");
const campoHasta = document.getElementById("campo-hasta");
const botonBuscar = document.getElementById("buscar");
const CAMPOS_GUARDADOS = ["producto", "litros", "consumo", "valor_hora"];

const pesos = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" });
const km = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 });

function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

// --- Preferencias del chofer: se recuerdan en este navegador ---

function leerPreferencias() {
  try {
    const guardado = JSON.parse(localStorage.getItem("nafteando") || "{}");
    for (const campo of CAMPOS_GUARDADOS) {
      if (guardado[campo] !== undefined) document.getElementById(campo).value = guardado[campo];
    }
  } catch (e) { /* sin almacenamiento: se usan los valores por defecto */ }
}

function guardarPreferencias() {
  try {
    const datos = {};
    for (const campo of CAMPOS_GUARDADOS) datos[campo] = document.getElementById(campo).value;
    localStorage.setItem("nafteando", JSON.stringify(datos));
  } catch (e) { /* no pasa nada si no se puede guardar */ }
}

// --- Modo cerca mío / con destino ---

function modo() {
  return formulario.querySelector("input[name=modo]:checked").value;
}

formulario.querySelectorAll("input[name=modo]").forEach((radio) =>
  radio.addEventListener("change", () => {
    campoHasta.hidden = modo() !== "destino";
    document.getElementById("hasta").required = modo() === "destino";
  })
);

// --- Ubicación del navegador ---

document.getElementById("ubicacion").addEventListener("click", () => {
  const boton = document.getElementById("ubicacion");
  if (!navigator.geolocation) {
    mostrarError("Tu navegador no comparte la ubicación. Escribí la dirección.");
    return;
  }
  boton.textContent = "Buscando…";
  navigator.geolocation.getCurrentPosition(
    (posicion) => {
      const { latitude, longitude } = posicion.coords;
      document.getElementById("desde").value = `${latitude.toFixed(6)},${longitude.toFixed(6)}`;
      boton.textContent = "Mi ubicación";
    },
    () => {
      boton.textContent = "Mi ubicación";
      mostrarError("No se pudo obtener tu ubicación. Escribí la dirección.");
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
});

// --- Mapa ---

const mapa = L.map("mapa").setView([-32.9468, -60.6393], 13);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(mapa);
const capa = L.layerGroup().addTo(mapa);

function marcador(lat, lon, color, radio, texto) {
  return L.circleMarker([lat, lon], {
    radius: radio, color, weight: 2, fillColor: color, fillOpacity: 0.85,
  }).bindPopup(texto).addTo(capa);
}

function textoEstacion(e) {
  return `<strong>${escapar(e.nombre)}</strong><br>${escapar(e.direccion)}<br>${pesos.format(e.precio)} por litro`;
}

async function mostrarEstaciones() {
  const producto = document.getElementById("producto").value;
  try {
    const respuesta = await fetch(`/api/estaciones?producto=${encodeURIComponent(producto)}`);
    const datos = await respuesta.json();
    capa.clearLayers();
    for (const e of datos.estaciones || []) marcador(e.latitud, e.longitud, "#64748b", 6, textoEstacion(e));
  } catch (e) { /* el mapa queda vacío */ }
}

function dibujarRecomendacion(rec) {
  capa.clearLayers();
  const puntos = [];
  const agregar = (lat, lon, color, radio, texto) => {
    marcador(lat, lon, color, radio, texto);
    puntos.push([lat, lon]);
  };
  agregar(rec.origen[0], rec.origen[1], "#2563eb", 8, "Salida");
  if (rec.destino) agregar(rec.destino[0], rec.destino[1], "#7c3aed", 8, "Destino");
  for (const o of rec.opciones) agregar(o.latitud, o.longitud, "#64748b", 6, textoEstacion(o));
  const ref = rec.referencia;
  agregar(ref.latitud, ref.longitud, "#d97706", 9, "Referencia<br>" + textoEstacion(ref));
  if (rec.mejor) agregar(rec.mejor.latitud, rec.mejor.longitud, "#16a34a", 11, "Conviene<br>" + textoEstacion(rec.mejor));
  mapa.fitBounds(puntos, { padding: [30, 30], maxZoom: 15 });
}

// --- Resultado ---

function mostrarError(mensaje) {
  resultado.hidden = false;
  resultado.innerHTML = `<p class="error">${escapar(mensaje)}</p>`;
}

function linkNavegacion(e) {
  return `https://www.google.com/maps/dir/?api=1&destination=${e.latitud},${e.longitud}`;
}

function mostrarRecomendacion(rec) {
  const ref = rec.referencia;
  let html;
  if (rec.conviene_desviarse) {
    const m = rec.mejor;
    let cuenta = `${pesos.format(m.ahorro_surtidor)} menos en el surtidor − ${pesos.format(m.costo_combustible_desvio)} de combustible por ${km.format(m.km_desvio)} km de desvío`;
    if (m.costo_tiempo > 0) cuenta += ` − ${pesos.format(m.costo_tiempo)} de tu tiempo`;
    html = `
      <p class="veredicto gana">Andá a ${escapar(m.nombre)}: ahorrás ${pesos.format(m.ahorro_neto)}</p>
      <p class="cuenta">${escapar(m.direccion)} · ${pesos.format(m.precio)}/L<br>${cuenta}</p>
      <a class="ir" href="${linkNavegacion(m)}" target="_blank" rel="noopener">Cómo llegar</a>`;
  } else {
    html = `
      <p class="veredicto">No te desvíes: cargá en ${escapar(ref.nombre)}</p>
      <p class="cuenta">${escapar(ref.direccion)} · ${pesos.format(ref.precio)}/L. Ninguna otra estación te ahorra plata una vez que contás el desvío.</p>
      <a class="ir" href="${linkNavegacion(ref)}" target="_blank" rel="noopener">Cómo llegar</a>`;
  }

  html += `<p class="cuenta">Comparado con ${escapar(ref.nombre)} (${pesos.format(ref.precio)}/L), la que te queda más a mano. Franja ${rec.franja.toLowerCase()}.</p>`;
  if (rec.opciones.length) {
    html += '<ul class="opciones">';
    for (const o of rec.opciones) {
      const clase = o.ahorro_neto > 0 ? "positivo" : "negativo";
      html += `<li>
        <span class="nombre">${escapar(o.nombre)}</span>
        <span class="ahorro ${clase}">${pesos.format(o.ahorro_neto)}</span>
        <span class="detalle">${pesos.format(o.precio)}/L · +${km.format(o.km_desvio)} km · +${Math.round(o.minutos_desvio)} min</span>
      </li>`;
    }
    html += "</ul>";
  }
  if (rec.aviso) html += `<p class="aviso">${escapar(rec.aviso)}.</p>`;
  else if (rec.estimado) html += '<p class="aviso">Distancias estimadas en línea recta.</p>';
  if (rec.aviso_datos) html += `<p class="aviso">${escapar(rec.aviso_datos)}.</p>`;

  resultado.innerHTML = html;
  resultado.hidden = false;
  dibujarRecomendacion(rec);
  resultado.scrollIntoView({ behavior: "smooth", block: "start" });
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  guardarPreferencias();
  const parametros = new URLSearchParams();
  for (const campo of ["desde", "producto", "litros", "consumo", "valor_hora"]) {
    parametros.set(campo, document.getElementById(campo).value);
  }
  if (modo() === "destino") parametros.set("hasta", document.getElementById("hasta").value);

  botonBuscar.disabled = true;
  botonBuscar.textContent = "Calculando…";
  try {
    const respuesta = await fetch(`/api/recomendar?${parametros}`);
    const datos = await respuesta.json();
    if (!respuesta.ok) mostrarError([datos.error || "No se pudo calcular.", datos.aviso_datos].filter(Boolean).join(". "));
    else mostrarRecomendacion(datos);
  } catch (e) {
    mostrarError("No hay conexión con el servidor.");
  } finally {
    botonBuscar.disabled = false;
    botonBuscar.textContent = "¿Dónde cargo?";
  }
});

document.getElementById("producto").addEventListener("change", mostrarEstaciones);

leerPreferencias();
mostrarEstaciones();
