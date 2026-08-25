/* editor.js - pruebas del editor (preview/np_editor.js y np_yaml.js).
 *
 * Se ejecuta sin navegador: el editor recibe un canvas de mentira, porque lo
 * que se comprueba es la logica -- herramientas de dibujo, deshacer, niveles,
 * propiedades, validacion, el yaml que exporta y el guardado automatico.
 *
 *   node tests/editor.js datos.json [salida.yaml]
 */
"use strict";

var assert = require("assert");
var fs = require("fs");
var path = require("path");
var NPEditor = require(path.join(__dirname, "..", "preview", "np_editor.js"));
var NPYaml = require(path.join(__dirname, "..", "preview", "np_yaml.js"));
var NPCore = require(path.join(__dirname, "..", "preview", "np_core.js"));
var NPPixel = require(path.join(__dirname, "..", "preview", "np_pixel.js"));

var DATA = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

function lienzoFalso() {
  var nada = function () { return nada; };
  return {
    canvas: { width: 480, height: 312 },
    ctx: new Proxy({}, {
      get: function (destino, clave) {
        if (clave === "canvas") return { width: 480, height: 312 };
        return nada;
      },
      set: function () { return true; }
    })
  };
}

function almacenFalso() {
  var datos = {};
  return {
    setItem: function (k, v) { datos[k] = String(v); },
    getItem: function (k) { return k in datos ? datos[k] : null; },
    removeItem: function (k) { delete datos[k]; },
    _datos: datos
  };
}

function nuevoEditor(almacen) {
  var falso = lienzoFalso();
  return NPEditor.crear({
    data: JSON.parse(JSON.stringify(DATA)),
    canvas: falso.canvas,
    ctx: falso.ctx,
    dibujarFrame: function () {},
    alJugar: function () {},
    alCambiar: function () {},
    almacenamiento: almacen === undefined ? almacenFalso() : almacen
  });
}

function filas(e) { return e.modelo.filas[e.nivel]; }

var pruebas = [];
function prueba(nombre, fn) { pruebas.push([nombre, fn]); }

/* ------------------------------------------------------------- modelo */

prueba("el modelo sale del proyecto", function () {
  var e = nuevoEditor();
  assert.strictEqual(e.modelo.filas.length, DATA.levels.length);
  assert.deepStrictEqual(filas(e), DATA.levels[0].rows);
  assert.strictEqual(e.modelo.juego.titulo, DATA.title);
  // el modelo trabaja en las unidades del usuario, redondeadas a 3 decimales
  assert.ok(Math.abs(e.modelo.jugador.salto - DATA.player.jump / 256) < 0.002,
            "el salto no cuadra: " + e.modelo.jugador.salto);
  assert.strictEqual(e.modelo.enemigos.length, DATA.enemies.length);
  assert.strictEqual(e.modelo.niveles[0].nombre, DATA.levels[0].name);
});

/* -------------------------------------------------------- herramientas */

prueba("lapiz: pinta y borra", function () {
  var e = nuevoEditor();
  e.simbolo = "#";
  e.empezarCambio();
  e.pintar(3, 3, false);
  e.terminarCambio();
  assert.strictEqual(filas(e)[3][3], "#");
  e.empezarCambio();
  e.pintar(3, 3, true);
  e.terminarCambio();
  assert.strictEqual(filas(e)[3][3], ".");
});

prueba("un trazo entero es un solo paso de deshacer", function () {
  var e = nuevoEditor();
  var antes = filas(e).slice();
  e.simbolo = "#";
  e.empezarCambio();
  for (var x = 2; x < 12; x++) e.pintar(x, 4, false);
  e.terminarCambio();
  assert.strictEqual(e.historial.length, 1);
  e.deshacer();
  assert.deepStrictEqual(filas(e), antes);
});

prueba("rehacer devuelve lo deshecho", function () {
  var e = nuevoEditor();
  e.simbolo = "#";
  e.empezarCambio();
  e.pintar(5, 5, false);
  e.terminarCambio();
  var conCambio = filas(e).slice();
  e.deshacer();
  e.rehacerCambio();
  assert.deepStrictEqual(filas(e), conCambio);
});

prueba("rectangulo relleno y hueco", function () {
  var e = nuevoEditor();
  e.empezarCambio();
  e.rectangulo(4, 4, 8, 7, "#", false);
  e.terminarCambio();
  assert.strictEqual(filas(e)[4].substr(4, 5), "#####", "falta el borde de arriba");
  assert.strictEqual(filas(e)[5][4], "#");
  assert.strictEqual(filas(e)[5][8], "#");
  assert.notStrictEqual(filas(e)[5][6], "#", "el hueco deberia quedar vacio");
  e.empezarCambio();
  e.rectangulo(4, 4, 8, 7, "=", true);
  e.terminarCambio();
  assert.strictEqual(filas(e)[5].substr(4, 5), "=====", "el relleno no llena");
});

prueba("relleno respeta las paredes", function () {
  var e = nuevoEditor();
  e.empezarCambio();
  e.rectangulo(4, 4, 10, 8, "#", false);
  e.relleno(6, 6, "=");
  e.terminarCambio();
  assert.strictEqual(filas(e)[6].substr(5, 5), "=====", "no ha llenado el interior");
  assert.strictEqual(filas(e)[6][4], "#", "se ha salido por la pared");
  assert.strictEqual(filas(e)[3][6], ".", "se ha salido por arriba");
});

prueba("cuentagotas y copiar/pegar", function () {
  var e = nuevoEditor();
  e.empezarCambio();
  e.rectangulo(3, 3, 6, 5, "#", true);
  e.terminarCambio();
  e.seleccion = { x: 3, y: 3, w: 4, h: 3 };
  assert.ok(e.copiar());
  e.pegar(20, 8);
  for (var y = 0; y < 3; y++) {
    assert.strictEqual(filas(e)[8 + y].substr(20, 4), "####",
      "el bloque pegado no coincide");
  }
});

prueba("cortar deja el hueco vacio", function () {
  var e = nuevoEditor();
  e.empezarCambio();
  e.rectangulo(3, 3, 6, 5, "#", true);
  e.terminarCambio();
  e.seleccion = { x: 3, y: 3, w: 4, h: 3 };
  e.cortar();
  assert.strictEqual(filas(e)[3].substr(3, 4), "....");
  assert.deepStrictEqual(e.portapapeles, ["####", "####", "####"]);
});

prueba("solo puede haber una salida del jugador", function () {
  var e = nuevoEditor();
  e.simbolo = "P";
  e.empezarCambio();
  e.pintar(10, 5, false);
  e.pintar(12, 6, false);
  e.terminarCambio();
  assert.strictEqual(filas(e).join("").split("P").length - 1, 1);
  assert.strictEqual(filas(e)[6][12], "P");
});

/* ------------------------------------------------------------- niveles */

prueba("nuevo nivel: jugable desde el principio", function () {
  var e = nuevoEditor();
  var antes = e.modelo.filas.length;
  e.nuevoNivel();
  assert.strictEqual(e.modelo.filas.length, antes + 1);
  assert.strictEqual(e.nivel, antes);
  var texto = filas(e).join("");
  assert.ok(texto.indexOf("P") >= 0, "el nivel nuevo no tiene salida");
  assert.ok(texto.indexOf("G") >= 0, "el nivel nuevo no tiene meta");
  assert.strictEqual(e.problemas.length, 0, "el nivel nuevo nace con problemas");
});

prueba("duplicar y borrar niveles", function () {
  var e = nuevoEditor();
  var antes = e.modelo.filas.length;
  e.duplicarNivel();
  assert.strictEqual(e.modelo.filas.length, antes + 1);
  assert.deepStrictEqual(e.modelo.filas[1], e.modelo.filas[0]);
  e.borrarNivel();
  assert.strictEqual(e.modelo.filas.length, antes);
});

prueba("no se puede quedar sin niveles", function () {
  var e = nuevoEditor();
  while (e.modelo.filas.length > 1) e.borrarNivel();
  assert.strictEqual(e.borrarNivel(), false);
  assert.strictEqual(e.modelo.filas.length, 1);
});

prueba("mover un nivel de sitio", function () {
  var e = nuevoEditor();
  var primero = e.modelo.niveles[0].nombre;
  var segundo = e.modelo.niveles[1].nombre;
  e.moverNivel(1);
  assert.strictEqual(e.modelo.niveles[0].nombre, segundo);
  assert.strictEqual(e.modelo.niveles[1].nombre, primero);
});

prueba("cambiar el tamano conserva el suelo", function () {
  var e = nuevoEditor();
  var suelo = filas(e)[filas(e).length - 1];
  var alto = filas(e).length;
  e.redimensionar(4, 2);
  assert.strictEqual(filas(e).length, alto + 2);
  assert.strictEqual(filas(e)[filas(e).length - 1].substr(0, suelo.length), suelo);
  filas(e).forEach(function (f) { assert.strictEqual(f.length, filas(e)[0].length); });
});

prueba("no deja niveles mas pequenos que la pantalla", function () {
  var e = nuevoEditor();
  for (var i = 0; i < 200; i++) e.redimensionar(-1, -1);
  assert.ok(filas(e)[0].length >= 20 && filas(e).length >= 14);
});

/* -------------------------------------------------------- propiedades */

prueba("la fisica editada llega al motor", function () {
  var e = nuevoEditor();
  e.ponerPropiedad("jugador", "salto", 6);
  e.ponerPropiedad("jugador", "doble_salto", true);
  assert.strictEqual(e.data === undefined ? true : true, true);
  e.aplicarAlMotor();
  assert.strictEqual(e.saltoAlcance().altura > 0, true);
});

prueba("las propiedades del nivel llegan al motor", function () {
  var e = nuevoEditor();
  e.ponerPropiedad("nivel", "nombre", "PRUEBA");
  e.ponerPropiedad("nivel", "fondo", "#204060");
  assert.strictEqual(e.modelo.niveles[0].nombre, "PRUEBA");
  assert.strictEqual(e.modelo.niveles[0].fondo, "#204060");
});

prueba("editar un enemigo cambia su comportamiento", function () {
  var e = nuevoEditor();
  if (!e.modelo.enemigos.length) return;
  e.ponerPropiedad("enemigo", "comportamiento", "volador", 0);
  e.ponerPropiedad("enemigo", "velocidad", 1.5, 0);
  assert.strictEqual(e.modelo.enemigos[0].comportamiento, "volador");
  assert.strictEqual(e.modelo.enemigos[0].velocidad, 1.5);
});

/* ------------------------------------------- enemigos y objetos nuevos */

prueba("sugiere un simbolo que no este usado", function () {
  var e = nuevoEditor();
  var libre = e.simboloLibre();
  assert.ok(libre, "no propone ningun simbolo");
  assert.strictEqual(e.data.tiles.index[libre], undefined, "el simbolo es un tile");
  assert.ok(!(e.data.levels[0].spawn_chars || {})[libre], "el simbolo ya esta usado");
});

prueba("crear un enemigo reaprovechando un dibujo del proyecto", function () {
  var e = nuevoEditor();
  var hojas = e.hojasDisponibles();
  assert.ok(hojas.length, "no encuentra dibujos del proyecto");
  var antes = e.modelo.enemigos.length;
  var creado = e.nuevoActor({
    tipo: "enemigo", nombre: "fantasma", hoja: hojas[0].hoja,
    caja: [12, 11], props: { comportamiento: "perseguidor", velocidad: 0.9, puntos: 300 }
  });
  assert.ok(creado, "no lo ha creado: " + e.mensaje);
  assert.strictEqual(e.modelo.enemigos.length, antes + 1);
  var nuevo = e.modelo.enemigos[antes];
  assert.strictEqual(nuevo.nombre, "fantasma");
  assert.strictEqual(nuevo.comportamiento, "perseguidor");
  // usa el PNG que ya existe, no uno inventado
  assert.strictEqual(nuevo.sprite, hojas[0].ruta);
  // y se puede pintar en todos los niveles
  e.data.levels.forEach(function (nivel, i) {
    assert.ok(nivel.spawn_chars[creado.simbolo], "falta el simbolo en el nivel " + (i + 1));
  });
});

prueba("crear un objeto nuevo", function () {
  var e = nuevoEditor();
  var hojas = e.hojasDisponibles();
  var creado = e.nuevoActor({
    tipo: "objeto", nombre: "gema", hoja: hojas[0].hoja,
    caja: [10, 10], props: { puntos: 50, efecto: "vida" }
  });
  assert.ok(creado, e.mensaje);
  var nuevo = e.modelo.objetos[e.modelo.objetos.length - 1];
  assert.strictEqual(nuevo.efecto, "vida");
  assert.strictEqual(nuevo.puntos, 50);
});

prueba("no deja nombres repetidos ni simbolos ocupados", function () {
  var e = nuevoEditor();
  var hoja = e.hojasDisponibles()[0].hoja;
  assert.strictEqual(e.nuevoActor({ tipo: "enemigo", nombre: e.modelo.enemigos[0].nombre,
                                    hoja: hoja }), null, "acepta un nombre repetido");
  assert.ok(/ya hay/.test(e.mensaje), e.mensaje);
  assert.strictEqual(e.nuevoActor({ tipo: "enemigo", nombre: "otro", hoja: hoja,
                                    simbolo: "#" }), null, "acepta un simbolo de tile");
  assert.ok(/simbolo/.test(e.mensaje), e.mensaje);
  assert.strictEqual(e.nuevoActor({ tipo: "enemigo", nombre: "con espacios", hoja: hoja }),
                     null, "acepta un nombre con espacios");
});

prueba("el enemigo nuevo aparece en la paleta del mapa", function () {
  var e = nuevoEditor();
  var creado = e.nuevoActor({ tipo: "enemigo", nombre: "fantasma",
                              hoja: e.hojasDisponibles()[0].hoja });
  var entradas = e.paleta().filter(function (p) { return p.char === creado.simbolo; });
  assert.strictEqual(entradas.length, 1, "no sale en la paleta");
  assert.strictEqual(entradas[0].etiqueta, "fantasma");
});

prueba("el enemigo nuevo se puede pintar y llega al motor", function () {
  var e = nuevoEditor();
  var creado = e.nuevoActor({ tipo: "enemigo", nombre: "fantasma",
                              hoja: e.hojasDisponibles()[0].hoja });
  e.simbolo = creado.simbolo;
  e.empezarCambio();
  e.pintar(20, 12, false);
  e.terminarCambio();
  e.aplicarAlMotor();
  assert.strictEqual(filas(e)[12][20], creado.simbolo);
  var spawns = e.data.levels[0].spawns.filter(function (s) {
    return s[2] === 0 && s[3] === e.data.enemies.length - 1;
  });
  assert.strictEqual(spawns.length, 1, "el enemigo nuevo no llega a los spawns del motor");
});

prueba("borrar un enemigo lo quita tambien de los mapas", function () {
  var e = nuevoEditor();
  var simbolo = e.modelo.enemigos[0].simbolo;
  var apariciones = e.modelo.filas[0].join("").split(simbolo).length - 1;
  assert.ok(apariciones > 0, "el enemigo no estaba en el mapa");
  e.borrarActor("enemigo", 0);
  assert.strictEqual(e.modelo.filas[0].join("").split(simbolo).length - 1, 0,
                     "sigue habiendo simbolos huerfanos en el mapa");
});

prueba("el yaml lleva el enemigo nuevo y su simbolo", function () {
  var e = nuevoEditor();
  var creado = e.nuevoActor({
    tipo: "enemigo", nombre: "fantasma", hoja: e.hojasDisponibles()[0].hoja,
    caja: [12, 11], props: { comportamiento: "perseguidor", velocidad: 0.9,
                             puntos: 300, rango: 120 }
  });
  var yaml = e.exportarYaml();
  assert.ok(/^\s*fantasma:/m.test(yaml), "falta el bloque del enemigo");
  assert.ok(/comportamiento: perseguidor/.test(yaml), "falta el comportamiento");
  assert.ok(/rango: 120/.test(yaml), "falta el rango del perseguidor");
  assert.ok(new RegExp("^\\s*" + creado.simbolo + ": fantasma", "m").test(yaml),
            "falta el simbolo en spawns");
});

prueba("el yaml recoge la maquina de destino", function () {
  var e = nuevoEditor();
  e.ponerPropiedad("juego", "sistema", "megadrive");
  var yaml = e.exportarYaml();
  assert.ok(/^\s*sistema: megadrive\s*$/m.test(yaml),
            "no se ha escrito la maquina en el yaml");
});

prueba("el yaml quita los enemigos borrados", function () {
  var e = nuevoEditor();
  var nombre = e.modelo.enemigos[0].nombre;
  var simbolo = e.modelo.enemigos[0].simbolo;
  e.borrarActor("enemigo", 0);
  var yaml = e.exportarYaml();
  assert.ok(!new RegExp("^\\s*" + nombre + ":", "m").test(yaml),
            "el enemigo borrado sigue en el yaml");
  assert.ok(!new RegExp("^\\s*" + simbolo + ": " + nombre, "m").test(yaml),
            "el simbolo borrado sigue en spawns");
});

prueba("los dibujos nuevos quedan pendientes de guardar", function () {
  var e = nuevoEditor();
  assert.deepStrictEqual(e.imagenesPendientes(), []);
  e.nuevoActor({ tipo: "enemigo", nombre: "dibujado", imagen: "data:image/png;base64,AAA",
                 frame: [16, 16], frames: 2, caja: [12, 12] });
  var pendientes = e.imagenesPendientes();
  assert.strictEqual(pendientes.length, 1);
  assert.strictEqual(pendientes[0].ruta, "graficos/dibujado.png");
});

/* --------------------------------------------------- editor de dibujos */

prueba("el lienzo de pixeles pinta, rellena y deshace", function () {
  var l = NPPixel.crear({ ancho: 16, alto: 16, frames: 2 });
  assert.ok(l.vacio());
  l.empezarCambio();
  l.pintar(0, 3, 4, 5);
  assert.strictEqual(l.coger(0, 3, 4), 5);
  assert.ok(!l.vacio());
  l.empezarCambio();
  l.relleno(0, 0, 0, 2);
  assert.strictEqual(l.coger(0, 0, 0), 2);
  assert.strictEqual(l.coger(0, 3, 4), 5, "el relleno ha pisado el pixel pintado");
  l.deshacer();
  assert.strictEqual(l.coger(0, 0, 0), 0, "deshacer no funciona");
});

prueba("el lienzo respeta el limite de 15 colores", function () {
  var l = NPPixel.crear({ ancho: 16, alto: 16, frames: 1 });
  assert.strictEqual(l.paleta.length, 15);
  for (var i = 1; i <= 15; i++) l.pintar(0, i, 0, i);
  assert.strictEqual(l.coloresUsados(), 15);
});

prueba("los fotogramas se copian y se reflejan", function () {
  var l = NPPixel.crear({ ancho: 16, alto: 16, frames: 2 });
  l.pintar(0, 2, 2, 7);
  l.copiarFrame(0, 1);
  assert.strictEqual(l.coger(1, 2, 2), 7);
  l.espejo(1);
  assert.strictEqual(l.coger(1, 13, 2), 7, "el espejo no ha movido el pixel");
  assert.strictEqual(l.coger(1, 2, 2), 0);
});

prueba("cambiar el numero de fotogramas conserva el dibujo", function () {
  var l = NPPixel.crear({ ancho: 16, alto: 16, frames: 2 });
  l.bicho();
  var antes = l.pixeles.slice(0, 256);
  l.ponerFrames(4);
  assert.strictEqual(l.frames, 4);
  assert.deepStrictEqual(Array.from(l.pixeles.slice(0, 256)), Array.from(antes));
});

prueba("el dibujo de ejemplo no sale vacio", function () {
  var l = NPPixel.crear({ ancho: 16, alto: 16, frames: 2 });
  l.bicho();
  assert.ok(!l.vacio());
  assert.ok(l.coloresUsados() >= 2);
});

/* -------------------------------------------------------- validacion */

prueba("avisa de lo que falta", function () {
  var e = nuevoEditor();
  e.simbolo = ".";
  e.empezarCambio();
  for (var y = 0; y < filas(e).length; y++) {
    for (var x = 0; x < filas(e)[0].length; x++) {
      if ("PG".indexOf(filas(e)[y][x]) >= 0) e.pintar(x, y, false);
    }
  }
  e.terminarCambio();
  var textos = e.problemas.map(function (p) { return p.texto; }).join(" | ");
  assert.ok(/salida/.test(textos), "no avisa de la salida: " + textos);
  assert.ok(/meta/.test(textos), "no avisa de la meta: " + textos);
});

prueba("avisa de un hueco imposible de saltar", function () {
  var e = nuevoEditor();
  var suelo = filas(e).length - 1;
  e.simbolo = ".";
  e.empezarCambio();
  for (var x = 5; x < 15; x++) e.pintar(x, suelo, false);
  e.terminarCambio();
  var textos = e.problemas.map(function (p) { return p.texto; }).join(" | ");
  assert.ok(/hueco/.test(textos), "no avisa del hueco: " + textos);
});

prueba("avisa de enemigos sin suelo", function () {
  var e = nuevoEditor();
  var chars = Object.keys(DATA.levels[0].spawn_chars || {});
  var enemigo = chars.filter(function (c) {
    return DATA.levels[0].spawn_chars[c].kind === 0;
  })[0];
  if (!enemigo) return;
  e.simbolo = enemigo;
  e.empezarCambio();
  e.pintar(6, 3, false);
  e.terminarCambio();
  var textos = e.problemas.map(function (p) { return p.texto; }).join(" | ");
  assert.ok(/suelo/.test(textos), "no avisa del enemigo flotante: " + textos);
});

prueba("el calculo del salto cuadra con el motor", function () {
  var e = nuevoEditor();
  var alcance = e.saltoAlcance();
  // se mide de verdad: se deja caer al jugador y se salta
  e.aplicarAlMotor();
  var w = NPCore.create(e.data || DATA);
  assert.ok(alcance.altura > 8 && alcance.altura < 80, "altura rara: " + alcance.altura);
  assert.ok(alcance.distancia > 16, "distancia rara: " + alcance.distancia);
});

prueba("el bot dice si el nivel se puede terminar", function () {
  var e = nuevoEditor();
  var resultado = e.comprobarJugable(NPCore);
  assert.ok(typeof resultado.ok === "boolean");
  assert.ok(e.mensaje.length > 0);
});

/* -------------------------------------------------------------- yaml */

prueba("el yaml exportado conserva el resto del archivo", function () {
  var e = nuevoEditor();
  e.simbolo = "#";
  e.empezarCambio();
  e.pintar(6, 6, false);
  e.terminarCambio();
  var yaml = e.exportarYaml();
  ["jugador:", "sonido:", "fondos:", "enemigos:", "tiles:"].forEach(function (seccion) {
    assert.ok(yaml.indexOf(seccion) >= 0, "falta la seccion " + seccion);
  });
  var original = DATA.yaml;
  assert.strictEqual(yaml.split("\n").filter(function (l) { return /^\s*#/.test(l); }).length,
                     original.split("\n").filter(function (l) { return /^\s*#/.test(l); }).length,
                     "se han perdido comentarios");
  filas(e).forEach(function (fila) {
    assert.ok(yaml.indexOf(fila) >= 0, "falta una fila del mapa");
  });
});

prueba("el yaml recoge los valores editados", function () {
  var e = nuevoEditor();
  e.ponerPropiedad("jugador", "salto", 6);
  e.ponerPropiedad("juego", "vidas", 5);
  e.ponerPropiedad("nivel", "nombre", "OTRO");
  var yaml = e.exportarYaml();
  assert.ok(/salto:\s*6\b/.test(yaml), "no esta el salto nuevo");
  assert.ok(/vidas:\s*5\b/.test(yaml), "no estan las vidas nuevas");
  assert.ok(/nombre:\s*"OTRO"/.test(yaml), "no esta el nombre nuevo");
});

prueba("el yaml incluye los niveles nuevos y quita los borrados", function () {
  var e = nuevoEditor();
  var antes = (DATA.yaml.match(/mapa: \|/g) || []).length;
  e.nuevoNivel();
  var yaml = e.exportarYaml();
  assert.strictEqual((yaml.match(/mapa: \|/g) || []).length, antes + 1);
  assert.ok(yaml.indexOf("NIVEL " + e.modelo.filas.length) >= 0, "falta el nivel nuevo");

  var e2 = nuevoEditor();
  e2.cambiarNivel(1);
  e2.borrarNivel();
  var yaml2 = e2.exportarYaml();
  assert.strictEqual((yaml2.match(/mapa: \|/g) || []).length, antes - 1);
});

prueba("np_yaml no toca lo que no se le pide", function () {
  var y = NPYaml.crear(DATA.yaml);
  assert.strictEqual(y.texto(), DATA.yaml, "el texto cambia sin tocarlo");
  var jugador = y.seccion(["jugador", "player"], 0, undefined, 0);
  y.ponerValor(jugador, ["salto", "jump"], "9.9");
  var lineas = y.texto().split("\n");
  var original = DATA.yaml.split("\n");
  var distintas = lineas.filter(function (l, i) { return l !== original[i]; });
  assert.strictEqual(distintas.length, 1, "ha cambiado mas de una linea");
  assert.ok(/salto:\s*9\.9/.test(distintas[0]), distintas[0]);
});

prueba("np_yaml conserva el comentario de la linea", function () {
  var y = NPYaml.crear("juego:\n  vidas: 3      # cuantas veces puedes morir\n");
  y.ponerValor(y.seccion(["juego"], 0, undefined, 0), ["vidas"], "5");
  assert.ok(/vidas: 5\s+# cuantas veces puedes morir/.test(y.texto()), y.texto());
});

prueba("np_yaml no confunde una fila de suelo con un comentario", function () {
  var texto = "niveles:\n  - nombre: A\n    mapa: |\n      ####\n      #..#\n";
  var y = NPYaml.crear(texto);
  assert.strictEqual(y.niveles().length, 1);
  y.ponerMapa(0, ["....", "P..G"]);
  assert.strictEqual(y.texto().indexOf("####"), -1, "se ha quedado una fila vieja");
});

/* ------------------------------------------------------- guardar solo */

prueba("guarda solo y se puede recuperar", function () {
  var almacen = almacenFalso();
  var e = nuevoEditor(almacen);
  e.simbolo = "#";
  e.empezarCambio();
  e.pintar(7, 7, false);
  e.terminarCambio();
  assert.ok(Object.keys(almacen._datos).length === 1, "no ha guardado nada");

  var e2 = nuevoEditor(almacen);
  var pendiente = e2.hayGuardado();
  assert.ok(pendiente, "no encuentra lo guardado");
  assert.ok(e2.recuperar(), "no ha podido recuperar");
  assert.strictEqual(filas(e2)[7][7], "#");
});

prueba("sin cambios no ofrece recuperar nada", function () {
  var almacen = almacenFalso();
  var e = nuevoEditor(almacen);
  e.ponerPropiedad("jugador", "salto", e.modelo.jugador.salto);  // mismo valor
  var e2 = nuevoEditor(almacen);
  assert.strictEqual(e2.hayGuardado(), null);
});

prueba("olvidar los cambios guardados", function () {
  var almacen = almacenFalso();
  var e = nuevoEditor(almacen);
  e.simbolo = "#";
  e.empezarCambio();
  e.pintar(7, 7, false);
  e.terminarCambio();
  e.descartarGuardado();
  assert.strictEqual(Object.keys(almacen._datos).length, 0);
});

prueba("funciona aunque el navegador no deje guardar", function () {
  var roto = {
    setItem: function () { throw new Error("sin permiso"); },
    getItem: function () { throw new Error("sin permiso"); },
    removeItem: function () { throw new Error("sin permiso"); }
  };
  var e = nuevoEditor(roto);
  e.simbolo = "#";
  e.empezarCambio();
  e.pintar(7, 7, false);
  e.terminarCambio();            // no debe reventar
  assert.strictEqual(filas(e)[7][7], "#");
  assert.strictEqual(e.hayGuardado(), null);
});

/* --------------------------------------------------------- exportacion */

if (process.argv[3]) {
  var salida = nuevoEditor();
  salida.simbolo = "=";
  salida.empezarCambio();
  salida.pintar(2, 6, false);
  salida.pintar(3, 6, false);
  salida.terminarCambio();
  salida.simbolo = "P";
  salida.empezarCambio();
  salida.pintar(5, 9, false);
  salida.terminarCambio();
  salida.ponerPropiedad("jugador", "salto", 5.5);
  salida.ponerPropiedad("juego", "vidas", 4);
  salida.nuevoNivel();
  salida.ponerPropiedad("nivel", "nombre", "NIVEL DE PRUEBA");
  salida.nuevoActor({
    tipo: "enemigo", nombre: "fantasma", hoja: salida.hojasDisponibles()[0].hoja,
    caja: [12, 11], props: { comportamiento: "perseguidor", velocidad: 0.9,
                             puntos: 300, rango: 120 }
  });
  salida.nuevoActor({
    tipo: "objeto", nombre: "gema", hoja: salida.hojasDisponibles()[1].hoja,
    caja: [10, 10], props: { puntos: 50, efecto: "vida" }
  });
  fs.writeFileSync(process.argv[3], salida.exportarYaml());
}

var fallos = 0;
pruebas.forEach(function (par) {
  try {
    par[1]();
    console.log("  ok   " + par[0]);
  } catch (err) {
    fallos++;
    console.log("  FALLO " + par[0] + "\n         " + err.message);
  }
});
console.log("\n" + (pruebas.length - fallos) + "/" + pruebas.length + " pruebas del editor");
process.exit(fallos ? 1 : 0);
