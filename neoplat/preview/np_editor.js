/* np_editor.js - editor de juegos dentro del propio preview.
 *
 * Edita el mapa (lapiz, rectangulo, relleno, seleccion, cuentagotas), las
 * propiedades de cada nivel, los ajustes del juego, la fisica del jugador y los
 * enemigos y objetos. Lo prueba al momento con el mismo motor que la consola y
 * devuelve el game.yaml con los cambios, conservando comentarios y formato.
 *
 * Todo el estado vive en un modelo propio (mapas en texto + valores en las
 * unidades que usa el usuario). De ahi salen dos cosas:
 *   - los datos que come el motor, con las mismas cuentas que el compilador
 *   - el game.yaml parcheado, con np_yaml.js
 */
(function (root) {
  "use strict";

  var TILE = 16;
  var MINI_ALTO = 40;                 // franja del minimapa
  var PASOS_HISTORIAL = 60;
  var VERSION_GUARDADO = 2;

  var NPYaml = (typeof require === "function" && typeof module !== "undefined")
    ? require("./np_yaml.js") : root.NPYaml;
  var NPBot = (typeof require === "function" && typeof module !== "undefined")
    ? require("./np_bot.js") : root.NPBot;

  var COMPORTAMIENTOS = ["patrulla", "volador", "perseguidor", "saltarin", "fijo"];
  var EFECTOS = ["puntos", "vida", "salud", "llave"];

  function fijoAUsuario(v) { return Math.round(v / 256 * 1000) / 1000; }
  function usuarioAFijo(v) { return Math.round(Number(v) * 256); }
  function clonar(x) { return JSON.parse(JSON.stringify(x)); }

  function crear(opciones) {
    var DATA = opciones.data;
    var canvas = opciones.canvas;
    var ctx = opciones.ctx;
    var dibujarFrame = opciones.dibujarFrame;
    var alJugar = opciones.alJugar || function () {};
    var alCambiar = opciones.alCambiar || function () {};
    var almacen = opciones.almacenamiento === undefined
      ? (typeof localStorage !== "undefined" ? localStorage : null)
      : opciones.almacenamiento;
    var claves = DATA.claves || { campos: {}, opciones: {}, rangos: {} };

    /* ------------------------------------------------------------ modelo */

    function modeloInicial() {
      var jugador = DATA.player;
      return {
        filas: DATA.levels.map(function (n) { return n.rows.slice(); }),
        niveles: DATA.levels.map(function (n) {
          return {
            nombre: n.name,
            fondo: n.background,
            musica: n.music ? (DATA.sonido.musica[n.music - 1] || {}).nombre || "" : "",
            capas: (n.layers || []).map(function (i) { return DATA.layers[i].name; })
          };
        }),
        juego: {
          titulo: DATA.title, autor: DATA.author,
          vidas: DATA.lives, tiempo: DATA.time_limit
        },
        jugador: {
          velocidad: fijoAUsuario(jugador.speed),
          aceleracion: fijoAUsuario(jugador.accel),
          friccion: fijoAUsuario(jugador.friction),
          control_aire: fijoAUsuario(jugador.air_accel),
          salto: fijoAUsuario(jugador.jump),
          corte_salto: fijoAUsuario(jugador.jump_cut),
          gravedad: fijoAUsuario(jugador.gravity),
          max_caida: fijoAUsuario(jugador.max_fall),
          rebote: fijoAUsuario(jugador.bounce),
          doble_salto: !!jugador.double_jump,
          pisar_enemigos: !!jugador.stomp,
          coyote: jugador.coyote,
          buffer_salto: jugador.jump_buffer,
          vida: jugador.health,
          invulnerable: jugador.invuln
        },
        enemigos: DATA.enemies.map(function (e) {
          return {
            nombre: e.name,
            comportamiento: COMPORTAMIENTOS[e.behavior] || "patrulla",
            velocidad: fijoAUsuario(e.speed),
            gravedad: fijoAUsuario(e.gravity),
            salto: fijoAUsuario(e.jump),
            rango: fijoAUsuario(e.range),
            amplitud: fijoAUsuario(e.amplitude),
            periodo: e.period, intervalo: e.interval, puntos: e.score,
            vida: e.health, dano: e.damage,
            pisable: !!e.stompable, girar_en_borde: !!e.edge_turn
          };
        }),
        objetos: DATA.items.map(function (o) {
          return {
            nombre: o.name, puntos: o.score,
            efecto: EFECTOS[o.effect] || "puntos", cantidad: o.amount
          };
        })
      };
    }

    var editor = {
      activo: false,
      nivel: 0,
      modelo: modeloInicial(),
      original: null,
      herramienta: "lapiz",
      simbolo: "#",
      zoom: 1,
      camX: 0,
      camY: 0,
      rejilla: true,
      guias: true,
      historial: [],
      rehacer: [],
      seleccion: null,          // {x, y, w, h}
      portapapeles: null,
      raton: { x: -1, y: -1, pulsando: false, boton: 0, inicio: null, arrastre: null },
      problemas: [],
      mensaje: "",
      guardadoPendiente: null
    };
    editor.original = clonar(editor.modelo);

    /* Al borrar un nivel el indice puede quedar fuera de rango durante un
       instante (el redibujado va por su cuenta), asi que se ajusta siempre. */
    function asegurarNivel() {
      var ultimo = editor.modelo.filas.length - 1;
      if (editor.nivel > ultimo) editor.nivel = ultimo;
      if (editor.nivel < 0) editor.nivel = 0;
    }

    function filas() { asegurarNivel(); return editor.modelo.filas[editor.nivel]; }
    function ancho() { return filas()[0].length; }
    function alto() { return filas().length; }
    function propsNivel() { asegurarNivel(); return editor.modelo.niveles[editor.nivel]; }

    function spawnChars() {
      asegurarNivel();
      var nivel = DATA.levels[editor.nivel];
      return (nivel && nivel.spawn_chars) || {};
    }
    function esSpawn(ch) { return !!spawnChars()[ch]; }
    function actorDe(ch) {
      var s = spawnChars()[ch];
      if (!s) return null;
      return (s.kind === 0 ? DATA.enemies : DATA.items)[s.def].actor;
    }
    function tipoDeTile(ch) {
      var i = DATA.tiles.index[ch];
      return i === undefined ? 0 : DATA.tiles.kind[i];
    }

    /* -------------------------------------------------- deshacer/rehacer */

    function instantanea() {
      return {
        nivel: editor.nivel,
        filas: editor.modelo.filas.map(function (f) { return f.slice(); }),
        niveles: clonar(editor.modelo.niveles),
        juego: clonar(editor.modelo.juego),
        jugador: clonar(editor.modelo.jugador),
        enemigos: clonar(editor.modelo.enemigos),
        objetos: clonar(editor.modelo.objetos)
      };
    }

    function restaurar(estado) {
      editor.nivel = Math.min(estado.nivel, estado.filas.length - 1);
      editor.modelo.filas = estado.filas.map(function (f) { return f.slice(); });
      editor.modelo.niveles = clonar(estado.niveles);
      editor.modelo.juego = clonar(estado.juego);
      editor.modelo.jugador = clonar(estado.jugador);
      editor.modelo.enemigos = clonar(estado.enemigos);
      editor.modelo.objetos = clonar(estado.objetos);
    }

    /** Abre un paso de deshacer. Un trazo entero cuenta como uno solo. */
    editor.empezarCambio = function () {
      editor.historial.push(instantanea());
      if (editor.historial.length > PASOS_HISTORIAL) editor.historial.shift();
      editor.rehacer.length = 0;
    };

    function cambioSuelto(fn) {
      editor.empezarCambio();
      fn();
      terminarCambio();
    }

    function terminarCambio() {
      revisar();
      guardar();
      alCambiar();
    }
    editor.terminarCambio = terminarCambio;

    editor.deshacer = function () {
      var previo = editor.historial.pop();
      if (!previo) return false;
      editor.rehacer.push(instantanea());
      restaurar(previo);
      terminarCambio();
      return true;
    };

    editor.rehacerCambio = function () {
      var siguiente = editor.rehacer.pop();
      if (!siguiente) return false;
      editor.historial.push(instantanea());
      restaurar(siguiente);
      terminarCambio();
      return true;
    };

    /* ------------------------------------------------------- dibujar mapa */

    function ponerChar(x, y, ch) {
      if (x < 0 || y < 0 || x >= ancho() || y >= alto()) return false;
      var fila = editor.modelo.filas[editor.nivel][y];
      if (fila[x] === ch) return false;
      if (ch === "P") quitarSalida();
      editor.modelo.filas[editor.nivel][y] =
        fila.substring(0, x) + ch + fila.substring(x + 1);
      return true;
    }

    function quitarSalida() {
      var f = editor.modelo.filas[editor.nivel];
      for (var y = 0; y < f.length; y++) {
        var x = f[y].indexOf("P");
        if (x >= 0) f[y] = f[y].substring(0, x) + "." + f[y].substring(x + 1);
      }
    }

    editor.ponerChar = ponerChar;

    editor.pintar = function (x, y, borrar) {
      ponerChar(x, y, borrar ? "." : editor.simbolo);
    };

    editor.rectangulo = function (x0, y0, x1, y1, ch, relleno) {
      var ax = Math.min(x0, x1), bx = Math.max(x0, x1);
      var ay = Math.min(y0, y1), by = Math.max(y0, y1);
      for (var y = ay; y <= by; y++) {
        for (var x = ax; x <= bx; x++) {
          var borde = (x === ax || x === bx || y === ay || y === by);
          if (relleno || borde) ponerChar(x, y, ch);
        }
      }
    };

    editor.relleno = function (x, y, ch) {
      if (x < 0 || y < 0 || x >= ancho() || y >= alto()) return;
      var objetivo = filas()[y][x];
      if (objetivo === ch) return;
      var pila = [[x, y]];
      var vistos = {};
      var limite = ancho() * alto();
      while (pila.length && limite-- > 0) {
        var punto = pila.pop();
        var px = punto[0], py = punto[1];
        if (px < 0 || py < 0 || px >= ancho() || py >= alto()) continue;
        var llave = px + "," + py;
        if (vistos[llave]) continue;
        vistos[llave] = 1;
        if (filas()[py][px] !== objetivo) continue;
        ponerChar(px, py, ch);
        pila.push([px + 1, py], [px - 1, py], [px, py + 1], [px, py - 1]);
      }
    };

    /* ------------------------------------------------------- seleccion */

    editor.copiar = function () {
      var s = editor.seleccion;
      if (!s) return false;
      var trozo = [];
      for (var y = 0; y < s.h; y++) {
        trozo.push(filas()[s.y + y].substr(s.x, s.w));
      }
      editor.portapapeles = trozo;
      editor.mensaje = "copiado " + s.w + "x" + s.h;
      return true;
    };

    editor.cortar = function () {
      if (!editor.copiar()) return false;
      cambioSuelto(function () {
        var s = editor.seleccion;
        editor.rectangulo(s.x, s.y, s.x + s.w - 1, s.y + s.h - 1, ".", true);
      });
      return true;
    };

    editor.pegar = function (x, y) {
      if (!editor.portapapeles) return false;
      cambioSuelto(function () {
        editor.portapapeles.forEach(function (fila, dy) {
          for (var dx = 0; dx < fila.length; dx++) ponerChar(x + dx, y + dy, fila[dx]);
        });
      });
      return true;
    };

    editor.borrarSeleccion = function () {
      var s = editor.seleccion;
      if (!s) return false;
      cambioSuelto(function () {
        editor.rectangulo(s.x, s.y, s.x + s.w - 1, s.y + s.h - 1, ".", true);
      });
      return true;
    };

    /* --------------------------------------------------- tamano y niveles */

    editor.redimensionar = function (dAncho, dAlto) {
      var w = ancho() + dAncho, h = alto() + dAlto;
      if (w < 20 || h < 14 || w > 512 || h > 256) return false;
      cambioSuelto(function () {
        var nuevas = filas().map(function (fila) {
          return dAncho >= 0 ? fila + Array(dAncho + 1).join(".") : fila.substring(0, w);
        });
        if (dAlto > 0) {
          var suelo = nuevas.pop();
          for (var i = 0; i < dAlto; i++) nuevas.push(Array(w + 1).join("."));
          nuevas.push(suelo);
        } else if (dAlto < 0) {
          var ultima = nuevas.pop();
          nuevas = nuevas.slice(0, h - 1);
          nuevas.push(ultima);
        }
        editor.modelo.filas[editor.nivel] = nuevas;
      });
      limitarCamara();
      return true;
    };

    function nivelVacio(nombre) {
      var w = 40, h = 16;
      var f = [];
      for (var y = 0; y < h - 1; y++) f.push(Array(w + 1).join("."));
      f.push(Array(w + 1).join("#"));
      var suelo = h - 2;
      f[suelo] = "P" + f[suelo].substring(1);
      f[suelo] = f[suelo].substring(0, w - 3) + "G" + f[suelo].substring(w - 2);
      return { filas: f, props: { nombre: nombre, fondo: "#101830", musica: "", capas: [] } };
    }

    editor.nuevoNivel = function () {
      cambioSuelto(function () {
        var nuevo = nivelVacio("NIVEL " + (editor.modelo.filas.length + 1));
        editor.modelo.filas.push(nuevo.filas);
        editor.modelo.niveles.push(nuevo.props);
        DATA.levels.push(nivelDATAVacio(nuevo));
      });
      editor.cambiarNivel(editor.modelo.filas.length - 1);
      return true;
    };

    function nivelDATAVacio(nuevo) {
      var modelo = DATA.levels[0];
      return {
        name: nuevo.props.nombre, width: nuevo.filas[0].length, height: nuevo.filas.length,
        cells: [], spawns: [], start: [16, 16], background: nuevo.props.fondo,
        layers: [], music: 0, rows: nuevo.filas.slice(),
        spawn_chars: clonar(modelo.spawn_chars)
      };
    }

    editor.duplicarNivel = function () {
      cambioSuelto(function () {
        var copia = filas().slice();
        var props = clonar(propsNivel());
        props.nombre = (props.nombre + " COPIA").substring(0, 20);
        editor.modelo.filas.splice(editor.nivel + 1, 0, copia);
        editor.modelo.niveles.splice(editor.nivel + 1, 0, props);
        var datosCopia = clonar(DATA.levels[editor.nivel]);
        datosCopia.name = props.nombre;
        DATA.levels.splice(editor.nivel + 1, 0, datosCopia);
      });
      editor.cambiarNivel(editor.nivel + 1);
      return true;
    };

    editor.borrarNivel = function () {
      if (editor.modelo.filas.length <= 1) {
        editor.mensaje = "tiene que quedar al menos un nivel";
        return false;
      }
      var quitado = editor.nivel;
      cambioSuelto(function () {
        editor.modelo.filas.splice(quitado, 1);
        editor.modelo.niveles.splice(quitado, 1);
        DATA.levels.splice(quitado, 1);
      });
      editor.cambiarNivel(Math.max(0, quitado - 1));
      return true;
    };

    editor.moverNivel = function (delta) {
      var destino = editor.nivel + delta;
      if (destino < 0 || destino >= editor.modelo.filas.length) return false;
      var actual = editor.nivel;
      cambioSuelto(function () {
        [["filas", editor.modelo.filas], ["niveles", editor.modelo.niveles],
         ["data", DATA.levels]].forEach(function (par) {
          var lista = par[1];
          var tmp = lista[actual];
          lista[actual] = lista[destino];
          lista[destino] = tmp;
        });
      });
      editor.cambiarNivel(destino);
      return true;
    };

    editor.cambiarNivel = function (indice) {
      if (indice < 0 || indice >= editor.modelo.filas.length) return;
      editor.nivel = indice;
      editor.seleccion = null;
      editor.camX = 0;
      editor.camY = Math.max(0, alto() * TILE - altoVista());
      limitarCamara();
      revisar();
      alCambiar();
    };

    /* --------------------------------------------- propiedades editables */

    editor.ponerPropiedad = function (grupo, campo, valor, indice) {
      cambioSuelto(function () {
        if (grupo === "nivel") editor.modelo.niveles[editor.nivel][campo] = valor;
        else if (grupo === "juego") editor.modelo.juego[campo] = valor;
        else if (grupo === "jugador") editor.modelo.jugador[campo] = valor;
        else if (grupo === "enemigo") editor.modelo.enemigos[indice][campo] = valor;
        else if (grupo === "objeto") editor.modelo.objetos[indice][campo] = valor;
      });
      aplicarAlMotor();
      return true;
    };

    /* ----------------------------------------------------- camara y zoom */

    function altoVista() { return (canvas.height - MINI_ALTO) / editor.zoom; }
    function anchoVista() { return canvas.width / editor.zoom; }

    function limitarCamara() {
      var maxX = Math.max(0, ancho() * TILE - anchoVista());
      var maxY = Math.max(0, alto() * TILE - altoVista());
      editor.camX = Math.max(0, Math.min(editor.camX, maxX));
      editor.camY = Math.max(0, Math.min(editor.camY, maxY));
    }
    editor.limitarCamara = limitarCamara;

    editor.mover = function (dx, dy) {
      editor.camX += dx;
      editor.camY += dy;
      limitarCamara();
    };

    editor.ponerZoom = function (zoom) {
      var centroX = editor.camX + anchoVista() / 2;
      var centroY = editor.camY + altoVista() / 2;
      editor.zoom = Math.max(0.5, Math.min(2, zoom));
      editor.camX = centroX - anchoVista() / 2;
      editor.camY = centroY - altoVista() / 2;
      limitarCamara();
    };

    editor.irA = function (px, py) {
      editor.camX = px - anchoVista() / 2;
      if (py !== undefined) editor.camY = py - altoVista() / 2;
      limitarCamara();
    };

    /* -------------------------------------------------------- validacion */

    function huecoMasLargo(f) {
      var suelo = f.length - 1;
      var mayor = 0, actual = 0, donde = -1, inicio = 0;
      for (var x = 0; x < f[suelo].length; x++) {
        var ch = f[suelo][x];
        var tipo = tipoDeTile(ch);
        if (tipo === 1 || tipo === 2) {
          actual = 0;
        } else {
          if (actual === 0) inicio = x;
          actual++;
          if (actual > mayor) { mayor = actual; donde = inicio; }
        }
      }
      return { ancho: mayor, x: donde };
    }

    function revisar() {
      asegurarNivel();
      var problemas = [];
      var f = filas();
      var texto = f.join("");
      var salidas = texto.split("P").length - 1;
      if (salidas === 0) {
        problemas.push({ texto: "falta la salida del jugador (P)", grave: true });
      } else if (salidas > 1) {
        problemas.push({ texto: "hay " + salidas + " salidas 'P'", grave: true });
      }
      var conMeta = false;
      for (var i = 0; i < DATA.tiles.chars.length; i++) {
        if (DATA.tiles.kind[i] === 4 && texto.indexOf(DATA.tiles.chars[i]) >= 0) conMeta = true;
      }
      if (!conMeta) problemas.push({ texto: "no hay meta: el nivel no se puede terminar", grave: true });

      var entidades = 0;
      var chars = spawnChars();
      for (var y = 0; y < f.length; y++) {
        for (var x = 0; x < f[y].length; x++) {
          var ch = f[y][x];
          var s = chars[ch];
          if (!s) continue;
          entidades++;
          if (s.kind === 0) {
            var enemigo = DATA.enemies[s.def];
            var conGravedad = enemigo.gravity > 0 && enemigo.behavior !== 1;
            var debajo = y + 1 < f.length ? tipoDeTile(f[y + 1][x]) : 0;
            if (conGravedad && debajo !== 1 && debajo !== 2) {
              problemas.push({
                texto: "un enemigo en (" + (x + 1) + "," + (y + 1) + ") no tiene suelo debajo",
                x: x * TILE, y: y * TILE
              });
            }
          }
        }
      }
      if (entidades > 64) {
        problemas.push({ texto: "hay " + entidades + " enemigos y objetos; el maximo es 64",
                         grave: true });
      }

      var hueco = huecoMasLargo(f);
      var alcance = Math.floor(saltoAlcance().distancia / TILE);
      if (hueco.ancho > alcance) {
        problemas.push({
          texto: "hay un hueco de " + hueco.ancho + " casillas y el salto cruza " + alcance,
          x: hueco.x * TILE, y: (f.length - 1) * TILE
        });
      }
      if (ancho() < 20 || alto() < 14) {
        problemas.push({ texto: "el nivel es mas pequeno que una pantalla", grave: true });
      }
      editor.problemas = problemas;
      return problemas;
    }
    editor.revisar = revisar;

    /** Altura y distancia que alcanza el salto con los ajustes actuales. */
    function saltoAlcance() {
      var j = editor.modelo.jugador;
      var g = Math.max(0.001, j.gravedad);
      var frames = 2 * j.salto / g;
      return {
        altura: Math.round(j.salto * j.salto / (2 * g)),
        distancia: Math.round(frames * j.velocidad)
      };
    }
    editor.saltoAlcance = saltoAlcance;

    /** Lanza el bot a ver si el nivel se puede terminar. */
    editor.comprobarJugable = function (NPCore) {
      aplicarAlMotor();
      var resultado = NPBot.jugar(NPCore, DATA, editor.nivel, { frames: 8000 });
      editor.mensaje = resultado.ok
        ? "el bot lo termina (" + Math.round(resultado.frames / 60) + " s, " +
          resultado.muertes + " muertes)"
        : "el bot no lo termina: " + resultado.motivo +
          (resultado.x !== undefined ? " (x=" + resultado.x + ")" : "");
      if (!resultado.ok && resultado.x !== undefined) editor.irA(resultado.x);
      alCambiar();
      return resultado;
    };

    /* ------------------------------------------- llevar todo al motor */

    function reconstruirNivel(indice) {
      var nivel = DATA.levels[indice];
      var f = editor.modelo.filas[indice];
      var props = editor.modelo.niveles[indice];
      var w = f[0].length, h = f.length;
      var vacio = DATA.tiles.index["."] !== undefined ? DATA.tiles.index["."] : 0;
      var celdas = [], spawns = [], salida = nivel.start;
      var pa = DATA.player.actor;
      var chars = nivel.spawn_chars || {};
      for (var y = 0; y < h; y++) {
        for (var x = 0; x < w; x++) {
          var ch = f[y][x];
          if (ch === "P") {
            celdas.push(vacio);
            salida = [Math.max(0, x * TILE + Math.floor((TILE - pa.box_w) / 2)),
                      Math.max(0, y * TILE + TILE - pa.box_h)];
            continue;
          }
          var s = chars[ch];
          if (s) {
            celdas.push(vacio);
            var actor = (s.kind === 0 ? DATA.enemies : DATA.items)[s.def].actor;
            spawns.push([Math.max(0, x * TILE + Math.floor((TILE - actor.box_w) / 2)),
                         Math.max(0, y * TILE + TILE - actor.box_h), s.kind, s.def]);
            continue;
          }
          var it = DATA.tiles.index[ch];
          celdas.push(it === undefined ? vacio : it);
        }
      }
      nivel.width = w;
      nivel.height = h;
      nivel.cells = celdas;
      nivel.spawns = spawns;
      nivel.start = salida;
      nivel.rows = f.slice();
      nivel.name = props.nombre;
      nivel.background = props.fondo;
      nivel.music = props.musica
        ? indiceMusica(props.musica) + 1
        : 0;
      nivel.layers = props.capas.map(indiceCapa).filter(function (i) { return i >= 0; });
    }

    function indiceMusica(nombre) {
      var lista = (DATA.sonido && DATA.sonido.musica) || [];
      for (var i = 0; i < lista.length; i++) if (lista[i].nombre === nombre) return i;
      return -1;
    }

    function indiceCapa(nombre) {
      for (var i = 0; i < DATA.layers.length; i++) if (DATA.layers[i].name === nombre) return i;
      return -1;
    }

    function aplicarAlMotor() {
      var j = editor.modelo.jugador;
      var p = DATA.player;
      p.speed = usuarioAFijo(j.velocidad);
      p.accel = usuarioAFijo(j.aceleracion);
      p.friction = usuarioAFijo(j.friccion);
      p.air_accel = usuarioAFijo(j.control_aire);
      p.jump = usuarioAFijo(j.salto);
      p.jump_cut = usuarioAFijo(j.corte_salto);
      p.gravity = usuarioAFijo(j.gravedad);
      p.max_fall = usuarioAFijo(j.max_caida);
      p.bounce = usuarioAFijo(j.rebote);
      p.double_jump = j.doble_salto ? 1 : 0;
      p.stomp = j.pisar_enemigos ? 1 : 0;
      p.coyote = Math.round(j.coyote);
      p.jump_buffer = Math.round(j.buffer_salto);
      p.health = Math.round(j.vida);
      p.invuln = Math.round(j.invulnerable);

      editor.modelo.enemigos.forEach(function (m, i) {
        var e = DATA.enemies[i];
        if (!e) return;
        e.behavior = Math.max(0, COMPORTAMIENTOS.indexOf(m.comportamiento));
        e.speed = usuarioAFijo(m.velocidad);
        e.gravity = usuarioAFijo(m.gravedad);
        e.jump = usuarioAFijo(m.salto);
        e.range = usuarioAFijo(m.rango);
        e.amplitude = usuarioAFijo(m.amplitud);
        e.period = Math.round(m.periodo);
        e.interval = Math.round(m.intervalo);
        e.score = Math.round(m.puntos);
        e.health = Math.round(m.vida);
        e.damage = Math.round(m.dano);
        e.stompable = m.pisable ? 1 : 0;
        e.edge_turn = m.girar_en_borde ? 1 : 0;
      });
      editor.modelo.objetos.forEach(function (m, i) {
        var o = DATA.items[i];
        if (!o) return;
        o.score = Math.round(m.puntos);
        o.effect = Math.max(0, EFECTOS.indexOf(m.efecto));
        o.amount = Math.round(m.cantidad);
      });
      DATA.title = editor.modelo.juego.titulo;
      DATA.author = editor.modelo.juego.autor;
      DATA.lives = Math.round(editor.modelo.juego.vidas);
      DATA.time_limit = Math.round(editor.modelo.juego.tiempo);
      for (var i = 0; i < editor.modelo.filas.length; i++) reconstruirNivel(i);
    }
    editor.aplicarAlMotor = aplicarAlMotor;

    editor.aplicar = function () {
      aplicarAlMotor();
      alJugar();
    };

    /* ------------------------------------------------ exportar el yaml */

    function cambio(a, b) { return JSON.stringify(a) !== JSON.stringify(b); }

    editor.exportarYaml = function () {
      var original = DATA.yaml || "";
      if (!original || !NPYaml) return editor.exportarMapas();
      var y = NPYaml.crear(original);
      var campos = claves.campos || {};
      var modelo = editor.modelo, base = editor.original;

      function escribir(rango, tabla, valores, previos) {
        if (!rango) return;
        Object.keys(tabla).forEach(function (campo) {
          if (!(campo in valores)) return;
          if (!cambio(valores[campo], previos ? previos[campo] : undefined)) return;
          y.ponerValor(rango, tabla[campo], formatear(campo, valores[campo]));
        });
      }

      function formatear(campo, valor) {
        if (typeof valor === "boolean") return NPYaml.siNo(valor);
        if (typeof valor === "number") return NPYaml.numero(valor, decimales(campo));
        if (campo === "titulo" || campo === "autor" || campo === "nombre" ||
            campo === "fondo") return NPYaml.entrecomillar(valor);
        return String(valor);
      }

      function decimales(campo) {
        var enteros = ["vidas", "tiempo", "coyote", "buffer_salto", "vida",
                       "invulnerable", "puntos", "dano", "periodo", "intervalo",
                       "cantidad", "rango", "amplitud"];
        return enteros.indexOf(campo) >= 0 ? 0 : 2;
      }

      escribir(y.seccion(["juego", "game"], 0, undefined, 0), campos.juego || {},
               modelo.juego, base.juego);
      escribir(y.seccion(["jugador", "player"], 0, undefined, 0), campos.jugador || {},
               modelo.jugador, base.jugador);

      var seccionEnemigos = y.seccion(["enemigos", "enemies"], 0, undefined, 0);
      if (seccionEnemigos) {
        modelo.enemigos.forEach(function (m, i) {
          var rango = y.seccion([m.nombre], seccionEnemigos.inicio, seccionEnemigos.fin);
          escribir(rango, campos.enemigo || {}, m, base.enemigos[i]);
        });
      }
      var seccionObjetos = y.seccion(["objetos", "items"], 0, undefined, 0);
      if (seccionObjetos) {
        modelo.objetos.forEach(function (m, i) {
          var rango = y.seccion([m.nombre], seccionObjetos.inicio, seccionObjetos.fin);
          escribir(rango, campos.objeto || {}, m, base.objetos[i]);
        });
      }

      // niveles: primero los que ya existian, luego se anaden o quitan
      var existentes = y.niveles().length;
      for (var i = modelo.filas.length; i < existentes; i++) {
        y.borrarNivel(modelo.filas.length);
      }
      for (var n = existentes; n < modelo.filas.length; n++) {
        y.insertarNivel(n, textoNivelNuevo(y, n));
      }
      modelo.filas.forEach(function (f, indice) {
        var props = modelo.niveles[indice];
        var previos = base.niveles[indice];
        var tabla = campos.nivel || {};
        ["nombre", "fondo", "musica"].forEach(function (campo) {
          if (!tabla[campo]) return;
          if (previos && !cambio(props[campo], previos[campo])) return;
          if (campo === "musica" && !props.musica) return;
          y.ponerValorNivel(indice, tabla[campo], formatear(campo, props[campo]));
        });
        if (tabla.fondos && (!previos || cambio(props.capas, previos.capas))) {
          y.ponerValorNivel(indice, tabla.fondos,
                            "[" + props.capas.join(", ") + "]");
        }
        y.ponerMapa(indice, f);
      });
      return y.texto();
    };

    function textoNivelNuevo(y, indice) {
      var props = editor.modelo.niveles[indice];
      var f = editor.modelo.filas[indice];
      var lineas = ['  - nombre: "' + props.nombre + '"',
                    '    fondo: "' + props.fondo + '"'];
      if (props.musica) lineas.push("    musica: " + props.musica);
      if (props.capas.length) lineas.push("    fondos: [" + props.capas.join(", ") + "]");
      lineas.push("    mapa: |");
      f.forEach(function (fila) { lineas.push("      " + fila); });
      return lineas.join("\n");
    }

    editor.exportarMapas = function () {
      return editor.modelo.filas.map(function (f, i) {
        return "# " + editor.modelo.niveles[i].nombre + "\n    mapa: |\n" +
               f.map(function (fila) { return "      " + fila; }).join("\n");
      }).join("\n\n");
    };

    /* ------------------------------------------------------ guardar solo */

    function llaveGuardado() {
      return "neoplat:" + (DATA.title || "juego");
    }

    function guardar() {
      if (!almacen) return;
      try {
        almacen.setItem(llaveGuardado(), JSON.stringify({
          version: VERSION_GUARDADO,
          cuando: Date.now(),
          modelo: editor.modelo
        }));
      } catch (e) { /* sin espacio o sin permiso: no pasa nada */ }
    }

    editor.hayGuardado = function () {
      if (!almacen) return null;
      try {
        var crudo = almacen.getItem(llaveGuardado());
        if (!crudo) return null;
        var datos = JSON.parse(crudo);
        if (datos.version !== VERSION_GUARDADO) return null;
        if (!cambio(datos.modelo, editor.original)) return null;
        return datos;
      } catch (e) { return null; }
    };

    editor.recuperar = function () {
      var datos = editor.hayGuardado();
      if (!datos) return false;
      editor.historial.push(instantanea());
      editor.modelo = datos.modelo;
      editor.nivel = Math.min(editor.nivel, editor.modelo.filas.length - 1);
      // los niveles anadidos tienen que existir tambien en DATA
      while (DATA.levels.length < editor.modelo.filas.length) {
        DATA.levels.push(nivelDATAVacio({
          filas: editor.modelo.filas[DATA.levels.length],
          props: editor.modelo.niveles[DATA.levels.length]
        }));
      }
      DATA.levels.length = editor.modelo.filas.length;
      aplicarAlMotor();
      revisar();
      alCambiar();
      return true;
    };

    editor.descartarGuardado = function () {
      if (!almacen) return;
      try { almacen.removeItem(llaveGuardado()); } catch (e) { /* nada */ }
    };

    /* --------------------------------------------------------- dibujado */

    function dibujarCapas() {
      asegurarNivel();
      var nivel = DATA.levels[editor.nivel];
      var capas = (nivel && nivel.layers) || [];
      for (var n = 0; n < capas.length; n++) {
        var L = DATA.layers[capas[n]];
        if (!L) continue;
        var scrollX = Math.floor(editor.camX * L.speed_x / 256);
        var col0 = scrollX >> 4, offX = scrollX & 15;
        var columnas = Math.ceil(anchoVista() / 16) + 1;
        for (var i = 0; i <= columnas; i++) {
          var col = col0 + i;
          if (L.repeat) col = ((col % L.cols) + L.cols) % L.cols;
          else if (col < 0 || col >= L.cols) continue;
          for (var r = 0; r < L.rows; r++)
            dibujarFrame(L.sheet, r * L.cols + col, i * 16 - offX,
                         L.offset_y + r * 16, false);
        }
      }
    }

    function dibujarMapa() {
      var col0 = Math.floor(editor.camX / TILE), row0 = Math.floor(editor.camY / TILE);
      var offX = editor.camX - col0 * TILE, offY = editor.camY - row0 * TILE;
      var columnas = Math.ceil(anchoVista() / TILE) + 1;
      var filasVisibles = Math.ceil(altoVista() / TILE) + 1;
      var f = filas();
      for (var c = 0; c <= columnas; c++) {
        for (var r = 0; r <= filasVisibles; r++) {
          var tx = col0 + c, ty = row0 + r;
          if (tx < 0 || tx >= ancho() || ty < 0 || ty >= alto()) continue;
          var ch = f[ty][tx];
          var x = c * TILE - offX, y = r * TILE - offY;
          if (ch === "P") {
            var pa = DATA.player.actor;
            dibujarFrame(pa.sheet, 0, x + Math.floor((TILE - pa.frame_w) / 2),
                         y + TILE - pa.frame_h, false);
            continue;
          }
          if (esSpawn(ch)) {
            var actor = actorDe(ch);
            dibujarFrame(actor.sheet, 0, x + Math.floor((TILE - actor.frame_w) / 2),
                         y + TILE - actor.frame_h, false);
            continue;
          }
          var indice = DATA.tiles.index[ch];
          if (indice === undefined) continue;
          dibujarFrame("__tiles__", DATA.tiles.gfx[indice], x, y, false);
        }
      }
    }

    function dibujarRejilla() {
      if (!editor.rejilla) return;
      var col0 = Math.floor(editor.camX / TILE), row0 = Math.floor(editor.camY / TILE);
      var offX = editor.camX - col0 * TILE, offY = editor.camY - row0 * TILE;
      ctx.strokeStyle = "rgba(255,255,255,0.10)";
      ctx.lineWidth = 1 / editor.zoom;
      ctx.beginPath();
      for (var x = -offX; x <= anchoVista(); x += TILE) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, altoVista());
      }
      for (var y = -offY; y <= altoVista(); y += TILE) {
        ctx.moveTo(0, y);
        ctx.lineTo(anchoVista(), y);
      }
      ctx.stroke();
    }

    /** Marca donde cae cada pantalla de 320x224, para componer por pantallas. */
    function dibujarGuias() {
      if (!editor.guias) return;
      ctx.strokeStyle = "rgba(242,183,5,0.35)";
      ctx.lineWidth = 1 / editor.zoom;
      ctx.beginPath();
      for (var x = 0; x <= ancho() * TILE; x += 320) {
        var px = x - editor.camX;
        if (px < -8 || px > anchoVista() + 8) continue;
        ctx.moveTo(px, 0);
        ctx.lineTo(px, altoVista());
      }
      ctx.stroke();
    }

    function dibujarSeleccion() {
      var s = editor.seleccion;
      if (!s) return;
      ctx.strokeStyle = "#58d0e8";
      ctx.lineWidth = 1 / editor.zoom;
      ctx.strokeRect(s.x * TILE - editor.camX, s.y * TILE - editor.camY,
                     s.w * TILE, s.h * TILE);
      ctx.fillStyle = "rgba(88,208,232,0.12)";
      ctx.fillRect(s.x * TILE - editor.camX, s.y * TILE - editor.camY,
                   s.w * TILE, s.h * TILE);
    }

    function dibujarCursor() {
      if (editor.raton.x < 0) return;
      var x = editor.raton.x * TILE - editor.camX;
      var y = editor.raton.y * TILE - editor.camY;
      // vista previa del rectangulo mientras se arrastra
      if (editor.raton.pulsando && editor.raton.inicio &&
          (editor.herramienta === "rect" || editor.herramienta === "seleccion")) {
        var ax = Math.min(editor.raton.inicio.x, editor.raton.x);
        var ay = Math.min(editor.raton.inicio.y, editor.raton.y);
        var bw = Math.abs(editor.raton.x - editor.raton.inicio.x) + 1;
        var bh = Math.abs(editor.raton.y - editor.raton.inicio.y) + 1;
        ctx.strokeStyle = editor.herramienta === "rect" ? "#f2b705" : "#58d0e8";
        ctx.lineWidth = 1 / editor.zoom;
        ctx.strokeRect(ax * TILE - editor.camX, ay * TILE - editor.camY,
                       bw * TILE, bh * TILE);
        return;
      }
      ctx.strokeStyle = "#f2b705";
      ctx.lineWidth = 1 / editor.zoom;
      ctx.strokeRect(x + 0.5, y + 0.5, TILE - 1, TILE - 1);
    }

    function dibujarMinimapa() {
      var y0 = canvas.height - MINI_ALTO;
      ctx.fillStyle = "rgba(10,10,16,0.94)";
      ctx.fillRect(0, y0, canvas.width, MINI_ALTO);
      var f = filas();
      var escala = Math.min(canvas.width / ancho(), (MINI_ALTO - 8) / alto());
      var offX = (canvas.width - ancho() * escala) / 2;
      for (var y = 0; y < alto(); y++) {
        for (var x = 0; x < ancho(); x++) {
          var ch = f[y][x];
          var color = null;
          if (ch === "P") color = "#f2b705";
          else if (esSpawn(ch)) color = spawnChars()[ch].kind ? "#f2d98a" : "#c4453c";
          else {
            var tipo = tipoDeTile(ch);
            if (tipo === 1) color = "#7d8ea8";
            else if (tipo === 2) color = "#b0834a";
            else if (tipo === 3) color = "#e0574f";
            else if (tipo === 4) color = "#58d0e8";
          }
          if (!color) continue;
          ctx.fillStyle = color;
          ctx.fillRect(offX + x * escala, y0 + 4 + y * escala,
                       Math.max(1, escala), Math.max(1, escala));
        }
      }
      ctx.strokeStyle = "rgba(255,255,255,0.7)";
      ctx.lineWidth = 1;
      ctx.strokeRect(offX + (editor.camX / TILE) * escala + 0.5,
                     y0 + 4.5 + (editor.camY / TILE) * escala,
                     (anchoVista() / TILE) * escala, (altoVista() / TILE) * escala);
      editor._mini = { y0: y0, escala: escala, offX: offX };
    }

    editor.dibujar = function () {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.fillStyle = propsNivel().fondo || "#000";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, canvas.width, canvas.height - MINI_ALTO);
      ctx.clip();
      ctx.scale(editor.zoom, editor.zoom);
      dibujarCapas();
      dibujarMapa();
      dibujarRejilla();
      dibujarGuias();
      dibujarSeleccion();
      dibujarCursor();
      ctx.restore();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      dibujarMinimapa();
    };

    /* ------------------------------------------------------------ raton */

    function aTile(px, py) {
      return {
        x: Math.floor((px / editor.zoom + editor.camX) / TILE),
        y: Math.floor((py / editor.zoom + editor.camY) / TILE)
      };
    }

    editor.pulsar = function (px, py, boton, conAlt) {
      if (py >= canvas.height - MINI_ALTO) {
        var mini = editor._mini;
        if (mini) {
          editor.irA(((px - mini.offX) / mini.escala) * TILE,
                     ((py - mini.y0 - 4) / mini.escala) * TILE);
        }
        return;
      }
      var t = aTile(px, py);
      editor.raton.pulsando = true;
      editor.raton.boton = boton;
      editor.raton.inicio = { x: t.x, y: t.y };
      editor.raton.arrastre = { px: px, py: py };

      if (conAlt || editor.herramienta === "cuentagotas") {
        var ch = (t.y >= 0 && t.y < alto() && t.x >= 0 && t.x < ancho())
          ? filas()[t.y][t.x] : null;
        if (ch) { editor.simbolo = ch; alCambiar(); }
        return;
      }
      if (editor.herramienta === "mano") return;
      if (editor.herramienta === "seleccion") {
        editor.seleccion = { x: t.x, y: t.y, w: 1, h: 1 };
        return;
      }
      if (editor.herramienta === "relleno") {
        editor.empezarCambio();
        editor.relleno(t.x, t.y, boton === 2 ? "." : editor.simbolo);
        terminarCambio();
        return;
      }
      if (editor.herramienta === "rect") return;   // se dibuja al soltar
      editor.empezarCambio();
      editor.pintar(t.x, t.y, boton === 2);
    };

    editor.mover_raton = function (px, py) {
      var t = aTile(px, py);
      editor.raton.x = t.x;
      editor.raton.y = t.y;
      if (!editor.raton.pulsando) return;
      if (editor.herramienta === "mano") {
        editor.mover((editor.raton.arrastre.px - px) / editor.zoom,
                     (editor.raton.arrastre.py - py) / editor.zoom);
        editor.raton.arrastre = { px: px, py: py };
        return;
      }
      if (editor.herramienta === "lapiz" && py < canvas.height - MINI_ALTO) {
        editor.pintar(t.x, t.y, editor.raton.boton === 2);
      }
    };

    editor.soltar = function () {
      if (!editor.raton.pulsando) return;
      var inicio = editor.raton.inicio;
      var fin = { x: editor.raton.x, y: editor.raton.y };
      editor.raton.pulsando = false;
      if (editor.herramienta === "rect" && inicio) {
        editor.empezarCambio();
        editor.rectangulo(inicio.x, inicio.y, fin.x, fin.y,
                          editor.raton.boton === 2 ? "." : editor.simbolo,
                          editor.raton.boton !== 2);
        terminarCambio();
      } else if (editor.herramienta === "seleccion" && inicio) {
        editor.seleccion = {
          x: Math.max(0, Math.min(inicio.x, fin.x)),
          y: Math.max(0, Math.min(inicio.y, fin.y)),
          w: Math.abs(fin.x - inicio.x) + 1,
          h: Math.abs(fin.y - inicio.y) + 1
        };
        editor.seleccion.w = Math.min(editor.seleccion.w, ancho() - editor.seleccion.x);
        editor.seleccion.h = Math.min(editor.seleccion.h, alto() - editor.seleccion.y);
        alCambiar();
      } else if (editor.herramienta === "lapiz") {
        terminarCambio();
      }
      editor.raton.inicio = null;
      editor.raton.arrastre = null;
    };

    /* ------------------------------------------------------------ paleta */

    editor.paleta = function () {
      var lista = [];
      lista.push({ char: "P", etiqueta: "salida", tipo: "jugador",
                   hoja: DATA.player.actor.sheet, frame: 0 });
      DATA.tiles.chars.forEach(function (ch, i) {
        if (ch === " ") return;
        var tipos = ["vacio", "solido", "plataforma", "peligro", "meta", "decorado"];
        lista.push({ char: ch, etiqueta: tipos[DATA.tiles.kind[i]] || "tile",
                     tipo: "tile", hoja: "__tiles__", frame: DATA.tiles.gfx[i] });
      });
      var chars = spawnChars();
      Object.keys(chars).forEach(function (ch) {
        var s = chars[ch];
        var nombres = s.kind === 0 ? DATA.nombres.enemigos : DATA.nombres.objetos;
        var actor = (s.kind === 0 ? DATA.enemies : DATA.items)[s.def].actor;
        lista.push({ char: ch, etiqueta: nombres[s.def] || (s.kind ? "objeto" : "enemigo"),
                     tipo: s.kind ? "objeto" : "enemigo", hoja: actor.sheet, frame: 0 });
      });
      return lista;
    };

    editor.entrar = function () {
      editor.activo = true;
      editor.camY = Math.max(0, alto() * TILE - altoVista());
      limitarCamara();
      revisar();
    };

    editor.salir = function () { editor.activo = false; };

    revisar();
    return editor;
  }

  var api = { crear: crear, MINI_ALTO: MINI_ALTO };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPEditor = api;
})(typeof window !== "undefined" ? window : this);
