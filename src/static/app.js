// Interfaz de Nafteando: arma el pedido, muestra la respuesta y el mapa.
// Toda la cuenta la hace el servidor (src/recomendador.py).

const $ = (id) => document.getElementById(id);
const formulario = $("formulario");
const resultado = $("resultado");
const CAMPOS_GUARDADOS = ["litros", "consumo", "valor_hora"];

const pesos = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 });
const pesosExactos = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" });
const km = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 });

// Puntos elegidos: { latitud, longitud, nombre } o null si solo hay texto.
const puntos = { desde: null, hasta: null };
let campoActivo = "desde";

function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

function bandera(e) {
  return e.bandera_corta || "Estación";
}

// "AV. CARLOS COLOMBRES 1552" -> "Av. Carlos Colombres 1552"
function capitalizar(texto) {
  return (texto || "").toLowerCase().replace(/(^|[\s(./])(\p{L})/gu, (_, antes, letra) => antes + letra.toUpperCase());
}

function titulo(e) {
  return `${bandera(e)} · ${capitalizar(e.direccion)}`;
}

function avisar(mensaje) {
  const aviso = $("aviso-flotante");
  aviso.textContent = mensaje;
  aviso.hidden = false;
  clearTimeout(avisar.temporizador);
  avisar.temporizador = setTimeout(() => (aviso.hidden = true), 3500);
}

function modo() {
  return formulario.querySelector("input[name=modo]:checked").value;
}

function elegido(nombre) {
  return formulario.querySelector(`input[name=${nombre}]:checked`).value;
}

// Nafta / Gasoil / GNC + común o premium -> el producto que usa el servidor.
function producto() {
  const tipo = elegido("tipo");
  const premium = elegido("calidad") === "premium";
  if (tipo === "gnc") return "gnc";
  if (tipo === "nafta") return premium ? "premium" : "super";
  return premium ? "gasoil premium" : "gasoil";
}

function franja() {
  return elegido("franja");
}

// Igual que el servidor: de 22 a 6 rige el precio nocturno.
function franjaPorHora() {
  const hora = new Date().getHours();
  return hora >= 22 || hora < 6 ? "Nocturno" : "Diurno";
}

function marcar(nombre, valor) {
  const opcion = formulario.querySelector(`input[name=${nombre}][value="${valor}"]`);
  if (opcion) opcion.checked = true;
}

const NOMBRES_PRODUCTO = {
  super: "Nafta súper", premium: "Nafta premium", gasoil: "Gasoil",
  "gasoil premium": "Gasoil premium", gnc: "GNC",
};

// --- Preferencias del chofer: se recuerdan en este navegador ---

function leerPreferencias() {
  try {
    const guardado = JSON.parse(localStorage.getItem("nafteando") || "{}");
    for (const campo of CAMPOS_GUARDADOS) {
      if (guardado[campo] !== undefined) $(campo).value = guardado[campo];
    }
    if (guardado.tipo) marcar("tipo", guardado.tipo);
    if (guardado.calidad) marcar("calidad", guardado.calidad);
    $("estimados").checked = Boolean(guardado.estimados);
  } catch (e) { /* sin almacenamiento: valores por defecto */ }
}

function guardarPreferencias() {
  try {
    const datos = { tipo: elegido("tipo"), calidad: elegido("calidad"), estimados: $("estimados").checked };
    for (const campo of CAMPOS_GUARDADOS) datos[campo] = $(campo).value;
    localStorage.setItem("nafteando", JSON.stringify(datos));
  } catch (e) { /* no pasa nada si no se puede guardar */ }
}

// --- Mapa ---

const mapa = L.map("mapa", { zoomControl: false }).setView(window.CENTRO, 13);
L.control.zoom({ position: "topleft" }).addTo(mapa);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(mapa);
const capaEstaciones = L.layerGroup().addTo(mapa);
// El tamaño del mapa lo define el CSS; Leaflet tiene que volver a medirlo.
new ResizeObserver(() => mapa.invalidateSize()).observe($("mapa"));
const pines = { desde: null, hasta: null };

function precioCorto(e) {
  return (e.estimado ? "≈" : "") + pesos.format(e.precio);
}

// Las estimadas son un punto hasta que se acerca el mapa; si no, con 80
// etiquetas no se lee nada.
const ZOOM_DETALLE = 15;

function iconoPrecio(e, clase = "") {
  if (e.estimado && !clase && mapa.getZoom() < ZOOM_DETALLE) {
    return L.divIcon({ className: "", html: '<span class="punto-estimado"></span>', iconSize: [10, 10], iconAnchor: [5, 5] });
  }
  return L.divIcon({
    className: "",
    html: `<span class="precio-mapa ${e.estimado ? "estimada" : ""} ${clase}">${precioCorto(e)}</span>`,
    iconSize: [0, 0],
  });
}

function fecha(texto) {
  // "2026-10-23 06:00:00" -> fecha local
  return new Date(texto.replace(" ", "T"));
}

function cuando(texto) {
  const d = fecha(texto);
  const hoy = new Date();
  const ayer = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 1);
  const hora = d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  if (d.toDateString() === hoy.toDateString()) return `hoy ${hora}`;
  if (d.toDateString() === ayer.toDateString()) return `ayer ${hora}`;
  return `el ${d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" })}`;
}

function explicacionEstimado(e) {
  return `Precio estimado ${escapar(e.base_estimacion)}. Esta estación informó ${pesosExactos.format(e.precio_informado)} por última vez ${cuando(e.vigente_desde)}.`;
}

function textoEstacion(e) {
  const razon = escapar(capitalizar(e.nombre.replace(/\s*\(.*\)$/, "")));
  const precio = e.estimado
    ? `≈ ${pesosExactos.format(e.precio)} por litro<br><small>${explicacionEstimado(e)}</small>`
    : `${pesosExactos.format(e.precio)} por litro<br><small>Informado ${cuando(e.vigente_desde)}</small>`;
  return `<strong>${escapar(titulo(e))}</strong><br>${razon}<br>${precio}`;
}

function dibujarEstaciones(estaciones, clases = {}) {
  estacionesActuales = estaciones;
  clasesActuales = clases;
  capaEstaciones.clearLayers();
  const informados = estaciones.filter((e) => !e.estimado).map((e) => e.precio);
  const minimo = informados.length ? Math.min(...informados) : null;
  const resaltando = Object.keys(clases).length > 0;
  for (const e of estaciones) {
    const clave = `${e.latitud},${e.longitud}`;
    const clase = clases[clave] ?? (resaltando ? "apagada" : !e.estimado && e.precio === minimo ? "barata" : "");
    const prioridad = clase === "mejor" ? 1000 : e.estimado ? 0 : 100;
    L.marker([e.latitud, e.longitud], { icon: iconoPrecio(e, clase), zIndexOffset: prioridad })
      .bindPopup(textoEstacion(e))
      .addTo(capaEstaciones);
  }
}

let estacionesActuales = [];
let clasesActuales = {};
mapa.on("zoomend", () => dibujarEstaciones(estacionesActuales, clasesActuales));

async function mostrarEstaciones() {
  const parametros = new URLSearchParams({ producto: producto(), franja: franja() });
  try {
    const respuesta = await fetch(`/api/estaciones?${parametros}`);
    const datos = await respuesta.json();
    const primeraVez = !estacionesActuales.length;
    estacionesActuales = datos.estaciones || [];
    dibujarEstaciones(estacionesActuales);
    // La primera vez se encuadran las estaciones con precio informado.
    const informadas = estacionesActuales.filter((e) => !e.estimado);
    if (primeraVez && informadas.length && !puntos.desde) {
      mapa.fitBounds(informadas.map((e) => [e.latitud, e.longitud]), { padding: [30, 30], maxZoom: 14 });
    }
    mostrarEstadoDatos(datos);
    mostrarRanking(estacionesActuales);
  } catch (e) { /* el mapa queda sin precios */ }
}

function mostrarEstadoDatos(datos) {
  const chip = $("estado-datos");
  chip.textContent = "";
  if (datos.muestra) {
    const dia = datos.aviso_datos && datos.aviso_datos.match(/\d{2}\/\d{2}\/\d{4}/);
    chip.textContent = dia ? `Precios al ${dia[0]}` : "Precios de muestra";
  } else if (datos.ultimo_informe) {
    chip.textContent = `Último precio: ${cuando(datos.ultimo_informe)}`;
  }
  chip.hidden = !chip.textContent;
}

function mostrarRanking(estaciones) {
  const informadas = estaciones.filter((e) => !e.estimado).length;
  $("titulo-lista").textContent = `${NOMBRES_PRODUCTO[producto()]}: ${estaciones.length} estaciones`;
  $("explicacion-lista").textContent =
    `${informadas} con precio informado y ${estaciones.length - informadas} estimadas (≈), horario ${franja().toLowerCase()}. Tocá una para verla en el mapa.`;
  const lista = $("ranking");
  lista.innerHTML = "";
  for (const e of [...estaciones].sort((a, b) => a.precio - b.precio)) {
    const li = document.createElement("li");
    li.className = e.estimado ? "estimada" : "";
    const detalle = e.estimado ? `estimado ${e.base_estimacion}` : `informado ${cuando(e.vigente_desde)}`;
    li.innerHTML = `
      <span class="nombre">${escapar(titulo(e))}</span>
      <span class="precio">${precioCorto(e)}</span>
      <span class="detalle">${escapar(detalle)}</span>`;
    li.addEventListener("click", () => {
      mapa.setView([e.latitud, e.longitud], 16);
      capaEstaciones.eachLayer((marcador) => {
        const { lat, lng } = marcador.getLatLng();
        if (lat === e.latitud && lng === e.longitud) marcador.openPopup();
      });
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    lista.appendChild(li);
  }
}

function ponerPin(campo) {
  const punto = puntos[campo];
  if (pines[campo]) {
    mapa.removeLayer(pines[campo]);
    pines[campo] = null;
  }
  if (!punto) return;
  const icono = L.divIcon({ className: "", html: `<div class="pin pin-${campo === "desde" ? "salida" : "destino"}"></div>`, iconSize: [22, 22], iconAnchor: [11, 11] });
  pines[campo] = L.marker([punto.latitud, punto.longitud], { icon: icono, draggable: true, zIndexOffset: 2000 })
    .addTo(mapa)
    .on("dragend", (evento) => {
      const { lat, lng } = evento.target.getLatLng();
      elegirPunto(campo, lat, lng, null);
    });
}

// --- Salida y destino ---

function campoLugar(campo) {
  return formulario.querySelector(`.campo-lugar[data-campo=${campo}]`);
}

function actualizarPista() {
  const nombre = campoActivo === "desde" ? "la <b>salida</b>" : "el <b>destino</b>";
  $("pista-mapa").innerHTML = `Tocá el mapa para marcar ${nombre}`;
  for (const campo of ["desde", "hasta"]) campoLugar(campo).classList.toggle("activo", campo === campoActivo);
}

async function elegirPunto(campo, latitud, longitud, nombre) {
  puntos[campo] = { latitud, longitud, nombre: nombre || "Punto marcado en el mapa" };
  $(campo).value = puntos[campo].nombre;
  campoLugar(campo).classList.add("con-punto");
  ocultarError();
  ponerPin(campo);
  if (campo === "desde" && modo() === "destino" && !puntos.hasta) {
    campoActivo = "hasta";
    actualizarPista();
  }
  if (!nombre) {
    // Se pone el nombre de la calle cuando llega, sin hacer esperar.
    try {
      const respuesta = await fetch(`/api/direccion?lat=${latitud}&lon=${longitud}`);
      const datos = await respuesta.json();
      if (datos.nombre && puntos[campo] && puntos[campo].latitud === latitud) {
        puntos[campo].nombre = datos.nombre;
        $(campo).value = datos.nombre;
      }
    } catch (e) { /* queda "Punto marcado en el mapa" */ }
  }
}

mapa.on("click", (evento) => {
  const campo = modo() === "destino" ? campoActivo : "desde";
  elegirPunto(campo, evento.latlng.lat, evento.latlng.lng, null);
});

for (const campo of ["desde", "hasta"]) {
  const entrada = $(campo);
  const lista = campoLugar(campo).querySelector(".sugerencias");
  let temporizador;
  let pedido = 0;

  entrada.addEventListener("focus", () => {
    campoActivo = campo;
    actualizarPista();
    if (puntos[campo] && puntos[campo].nombre === entrada.value) entrada.select();
  });

  entrada.addEventListener("input", () => {
    // Si escribe, el punto anterior deja de valer hasta que elija otro.
    puntos[campo] = null;
    ponerPin(campo);
    campoLugar(campo).classList.remove("con-punto");
    clearTimeout(temporizador);
    const texto = entrada.value.trim();
    if (texto.length < 3) {
      lista.hidden = true;
      return;
    }
    temporizador = setTimeout(async () => {
      const este = ++pedido;
      try {
        const respuesta = await fetch(`/api/sugerencias?q=${encodeURIComponent(texto)}`);
        const datos = await respuesta.json();
        if (este !== pedido) return;
        mostrarSugerencias(campo, datos.sugerencias || []);
      } catch (e) { lista.hidden = true; }
    }, 350);
  });

  entrada.addEventListener("keydown", (evento) => {
    const opciones = [...lista.querySelectorAll("li")];
    if (lista.hidden || !opciones.length) return;
    const actual = opciones.findIndex((li) => li.getAttribute("aria-selected") === "true");
    if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
      evento.preventDefault();
      const siguiente = (actual + (evento.key === "ArrowDown" ? 1 : -1) + opciones.length) % opciones.length;
      opciones.forEach((li, i) => li.setAttribute("aria-selected", i === siguiente));
    } else if (evento.key === "Enter" && actual >= 0) {
      evento.preventDefault();
      opciones[actual].click();
    } else if (evento.key === "Escape") {
      lista.hidden = true;
    }
  });

  entrada.addEventListener("blur", () => setTimeout(() => (lista.hidden = true), 200));
}

function mostrarSugerencias(campo, sugerencias) {
  const lista = campoLugar(campo).querySelector(".sugerencias");
  lista.innerHTML = "";
  if (!sugerencias.length) {
    lista.hidden = true;
    return;
  }
  for (const s of sugerencias) {
    const li = document.createElement("li");
    li.setAttribute("role", "option");
    li.textContent = s.nombre;
    li.addEventListener("mousedown", (evento) => evento.preventDefault());
    li.addEventListener("click", () => {
      lista.hidden = true;
      elegirPunto(campo, s.latitud, s.longitud, s.nombre);
      mapa.setView([s.latitud, s.longitud], Math.max(mapa.getZoom(), 15));
    });
    lista.appendChild(li);
  }
  lista.hidden = false;
}

formulario.querySelectorAll("input[name=modo]").forEach((radio) =>
  radio.addEventListener("change", () => {
    const conDestino = modo() === "destino";
    $("campo-hasta").hidden = !conDestino;
    if (!conDestino) {
      puntos.hasta = null;
      ponerPin("hasta");
      campoActivo = "desde";
    } else if (puntos.desde) {
      campoActivo = "hasta";
      $("hasta").focus();
    }
    actualizarPista();
  })
);

// --- Ubicación del teléfono ---

function ubicarme() {
  const botones = [$("ubicarme"), $("ubicarme-mapa")];
  if (!navigator.geolocation || !window.isSecureContext) {
    mostrarError("Este navegador no comparte la ubicación. Escribí la dirección o tocá el mapa.");
    return;
  }
  botones.forEach((b) => b.classList.add("buscando"));
  navigator.geolocation.getCurrentPosition(
    (posicion) => {
      botones.forEach((b) => b.classList.remove("buscando"));
      const { latitude, longitude } = posicion.coords;
      elegirPunto("desde", latitude, longitude, null);
      $("desde").value = "Tu ubicación";
      mapa.setView([latitude, longitude], 15);
      avisar("Listo: salís desde tu ubicación");
    },
    (error) => {
      botones.forEach((b) => b.classList.remove("buscando"));
      const mensajes = {
        1: "No diste permiso para usar tu ubicación. Activalo en el candado de la barra de direcciones, o tocá el mapa.",
        2: "No se pudo saber dónde estás. Probá de nuevo o tocá el mapa.",
        3: "La ubicación tardó demasiado. Probá de nuevo o tocá el mapa.",
      };
      mostrarError(mensajes[error.code] || mensajes[2]);
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
  );
}
$("ubicarme").addEventListener("click", ubicarme);
$("ubicarme-mapa").addEventListener("click", ubicarme);

// --- Litros y consumo ---

formulario.querySelectorAll("[data-paso]").forEach((boton) =>
  boton.addEventListener("click", () => {
    const entrada = $(boton.dataset.paso);
    const valor = (parseFloat(entrada.value) || 0) + Number(boton.dataset.delta);
    entrada.value = Math.max(1, valor);
  })
);

// --- Resultado ---

function mostrarError(mensaje) {
  const error = $("error-lugar");
  error.textContent = mensaje;
  error.hidden = false;
}

function ocultarError() {
  $("error-lugar").hidden = true;
}

function linkNavegacion(estacion, rec) {
  const parametros = new URLSearchParams({ api: "1", travelmode: "driving" });
  parametros.set("origin", `${rec.origen[0]},${rec.origen[1]}`);
  if (rec.destino) {
    parametros.set("destination", `${rec.destino[0]},${rec.destino[1]}`);
    parametros.set("waypoints", `${estacion.latitud},${estacion.longitud}`);
  } else {
    parametros.set("destination", `${estacion.latitud},${estacion.longitud}`);
  }
  return `https://www.google.com/maps/dir/?${parametros}`;
}

const ICONO_IR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.7 11.3 12.7 2.3a1 1 0 0 0-1.4 0l-9 9a1 1 0 0 0 0 1.4l9 9a1 1 0 0 0 1.4 0l9-9a1 1 0 0 0 0-1.4ZM14 14.5V12h-4v3H8v-4a1 1 0 0 1 1-1h5V7.5l3.5 3.5Z"/></svg>';

function mostrarRecomendacion(rec) {
  const ref = rec.referencia;
  const mejor = rec.mejor;
  let html;

  if (mejor) {
    html = `
      <article class="tarjeta veredicto">
        <p class="etiqueta">Conviene desviarte · ahorrás</p>
        <p class="monto">${pesos.format(mejor.ahorro_neto)}</p>
        <p class="lugar">${escapar(titulo(mejor))}${mejor.estimado ? '<span class="marca-estimado">precio estimado</span>' : ""}<small>${mejor.estimado ? "≈ " : ""}${pesosExactos.format(mejor.precio)}/L · +${km.format(mejor.km_desvio)} km de desvío</small></p>
        <div class="acciones"><a class="ir" href="${linkNavegacion(mejor, rec)}" target="_blank" rel="noopener">${ICONO_IR} Cómo llegar</a></div>
      </article>
      <article class="tarjeta">
        <h2>La cuenta</h2>
        <ul class="cuenta">
          <li><span>Pagás menos en el surtidor</span><span class="positivo">+${pesosExactos.format(mejor.ahorro_surtidor)}</span></li>
          <li><span>Combustible del desvío (${km.format(mejor.km_desvio)} km)</span><span class="negativo">−${pesosExactos.format(mejor.costo_combustible_desvio)}</span></li>
          ${mejor.costo_tiempo > 0 ? `<li><span>Tu tiempo (${Math.round(mejor.minutos_desvio)} min)</span><span class="negativo">−${pesosExactos.format(mejor.costo_tiempo)}</span></li>` : ""}
          <li><span>Ahorro neto</span><span class="positivo">${pesosExactos.format(mejor.ahorro_neto)}</span></li>
        </ul>
        <p class="nota">Comparado con cargar en ${escapar(titulo(ref))} a ${pesosExactos.format(ref.precio)}/L, la que te queda más a mano.</p>
      </article>`;
  } else {
    html = `
      <article class="tarjeta veredicto neutro">
        <p class="etiqueta">No te conviene desviarte</p>
        <p class="titulo">Cargá en ${escapar(titulo(ref))}${ref.estimado ? '<span class="marca-estimado">precio estimado</span>' : ""}</p>
        <p class="lugar"><small>${pesosExactos.format(ref.precio)}/L · la que te queda más a mano</small></p>
        <div class="acciones"><a class="ir" href="${linkNavegacion(ref, rec)}" target="_blank" rel="noopener">${ICONO_IR} Cómo llegar</a></div>
      </article>
      <p class="nota">Ninguna otra estación te ahorra plata una vez que contás lo que gastás en llegar.</p>`;
  }

  if (rec.opciones.length) {
    html += '<article class="tarjeta"><h2>Todas las opciones</h2><ul class="opciones">';
    rec.opciones.forEach((o, i) => {
      const gana = o.ahorro_neto > 0;
      html += `<li class="${gana ? "gana" : ""}">
        <span class="numero">${i + 1}</span>
        <span class="nombre">${escapar(titulo(o))}${o.estimado ? '<span class="marca-estimado">≈ estimado</span>' : ""}</span>
        <span class="ahorro ${gana ? "positivo" : "negativo"}">${gana ? "+" : ""}${pesos.format(o.ahorro_neto)}</span>
        <span class="detalle">${pesosExactos.format(o.precio)}/L · +${km.format(o.km_desvio)} km · +${Math.round(o.minutos_desvio)} min</span>
      </li>`;
    });
    html += "</ul></article>";
  }

  const avisos = [rec.aviso, !rec.aviso && rec.estimado ? "Distancias estimadas en línea recta" : null, rec.aviso_datos].filter(Boolean);
  for (const aviso of avisos) html += `<p class="aviso">${escapar(aviso)}.</p>`;

  resultado.innerHTML = html;
  resultado.hidden = false;
  dibujarRecomendacion(rec);
  resultado.scrollIntoView({ behavior: "smooth", block: "start" });
}

function dibujarRecomendacion(rec) {
  const clases = {};
  for (const o of rec.opciones) clases[`${o.latitud},${o.longitud}`] = "";
  clases[`${rec.referencia.latitud},${rec.referencia.longitud}`] = "referencia";
  if (rec.mejor) clases[`${rec.mejor.latitud},${rec.mejor.longitud}`] = "mejor";
  dibujarEstaciones([rec.referencia, ...rec.opciones], clases);

  puntos.desde = puntos.desde || { latitud: rec.origen[0], longitud: rec.origen[1], nombre: $("desde").value };
  ponerPin("desde");
  if (rec.destino) {
    puntos.hasta = puntos.hasta || { latitud: rec.destino[0], longitud: rec.destino[1], nombre: $("hasta").value };
    ponerPin("hasta");
  }
  const limites = [rec.origen, [rec.referencia.latitud, rec.referencia.longitud]];
  if (rec.destino) limites.push(rec.destino);
  if (rec.mejor) limites.push([rec.mejor.latitud, rec.mejor.longitud]);
  mapa.fitBounds(limites, { padding: [50, 50], maxZoom: 15 });
}

function valorLugar(campo) {
  const punto = puntos[campo];
  return punto ? `${punto.latitud},${punto.longitud}` : $(campo).value.trim();
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  ocultarError();
  if (!valorLugar("desde")) {
    mostrarError("Poné desde dónde salís: escribí una dirección, usá tu ubicación o tocá el mapa.");
    $("desde").focus();
    return;
  }
  if (modo() === "destino" && !valorLugar("hasta")) {
    mostrarError("Poné a dónde vas, o elegí \"Cerca mío\".");
    $("hasta").focus();
    return;
  }
  guardarPreferencias();

  const parametros = new URLSearchParams({
    desde: valorLugar("desde"),
    producto: producto(),
    franja: franja(),
    estimados: $("estimados").checked ? "1" : "0",
    litros: $("litros").value,
    consumo: $("consumo").value,
    valor_hora: $("valor_hora").value,
  });
  if (modo() === "destino") parametros.set("hasta", valorLugar("hasta"));

  const boton = $("buscar");
  boton.disabled = true;
  boton.querySelector(".texto-boton").textContent = "Calculando…";
  try {
    const respuesta = await fetch(`/api/recomendar?${parametros}`);
    const datos = await respuesta.json();
    if (!respuesta.ok) {
      resultado.hidden = true;
      mostrarError(datos.error || "No se pudo calcular.");
    } else {
      mostrarRecomendacion(datos);
    }
  } catch (e) {
    mostrarError("No hay conexión con el servidor. Probá de nuevo.");
  } finally {
    boton.disabled = false;
    boton.querySelector(".texto-boton").textContent = "¿Dónde cargo?";
  }
});

function actualizarCalidad() {
  $("calidad").hidden = elegido("tipo") === "gnc";
}

formulario.querySelectorAll("input[name=tipo], input[name=calidad], input[name=franja]").forEach((radio) =>
  radio.addEventListener("change", () => {
    actualizarCalidad();
    resultado.hidden = true;
    mostrarEstaciones();
  })
);
$("estimados").addEventListener("change", () => (resultado.hidden = true));

marcar("franja", franjaPorHora());
$("pista-franja").textContent = `· ahora rige el ${franjaPorHora().toLowerCase()}`;

leerPreferencias();
actualizarCalidad();
actualizarPista();
mostrarEstaciones();
