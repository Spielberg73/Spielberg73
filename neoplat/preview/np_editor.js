/* np_editor.js - editor de niveles dentro del propio preview.
 *
 * Pintas el mapa con el raton (o con el dedo), colocas enemigos y objetos,
 * pruebas el nivel al momento y te llevas el game.yaml ya modificado.
 *
 * El editor trabaja siempre sobre el mapa en texto (las mismas filas de
 * caracteres del game.yaml), que es la fuente de la verdad: al pulsar "jugar"
 * reconstruye los datos del nivel igual que hace el compilador, de modo que lo
 * que pruebas es exactamente lo que se compilara para la consola.
 */
(function (root) {
  "use strict";

  var TILE = 16;
  var MINI_ALTO = 34;              // franja del minimapa, abajo del todo

  function crear(opciones) {
    var DATA = opciones.data;
    var canvas = opciones.canvas;
    var ctx = opciones.ctx;
    var dibujarFrame = opciones.dibujarFrame;      // (hoja, frame, x, y, flip)
    var alJugar = opciones.alJugar || function () {};
    var alCambiar = opciones.alCambiar || function () {};

    var editor = {
      activo: false,
      nivel: 0,
      filas: DATA.levels.map(function (n) { return n.rows.slice(); }),
      herramienta: "#",
      camX: 0,
      camY: 0,
      rejilla: true,
      historial: [],
      raton: { x: -1, y: -1, pulsando: false, arrastrando: false },
      aviso: ""
    };

    /* ------------------------------------------------------------ ayudas */

    function filas() { return editor.filas[editor.nivel]; }
    function ancho() { return filas()[0].length; }
    function alto() { return filas().length; }

    function esSpawn(ch) {
      return !!DATA.levels[editor.nivel].spawn_chars[ch];
    }

    function actorDe(ch) {
      var s = DATA.levels[editor.nivel].spawn_chars[ch];
      if (!s) return null;
      return (s.kind === 0 ? DATA.enemies : DATA.items)[s.def].actor;
    }

    function guardarHistorial() {
      editor.historial.push({ nivel: editor.nivel, filas: filas().slice() });
      if (editor.historial.length > 80) editor.historial.shift();
    }

    editor.deshacer = function () {
      var previo = editor.historial.pop();
      if (!previo) return false;
      editor.nivel = previo.nivel;
      editor.filas[previo.nivel] = previo.filas;
      alCambiar();
      return true;
    };

    /* ------------------------------------------------------------ pintar */

    function ponerChar(x, y, ch) {
      var fila = filas()[y];
      filas()[y] = fila.substring(0, x) + ch + fila.substring(x + 1);
    }

    editor.pintar = function (x, y, borrar) {
      if (x < 0 || y < 0 || x >= ancho() || y >= alto()) return;
      var ch = borrar ? "." : editor.herramienta;
      var actual = filas()[y][x];
      if (actual === ch) return;
      guardarHistorial();
      if (ch === "P") {
        // solo puede haber una salida: se quita la anterior
        for (var fy = 0; fy < alto(); fy++) {
          var fx = filas()[fy].indexOf("P");
          if (fx >= 0) ponerChar(fx, fy, ".");
        }
      }
      ponerChar(x, y, ch);
      editor.aviso = comprobar();
      alCambiar();
    };

    function comprobar() {
      var texto = filas().join("");
      if (texto.indexOf("P") < 0) return "falta la salida del jugador (P)";
      var conMeta = false;
      for (var i = 0; i < DATA.tiles.chars.length; i++)
        if (DATA.tiles.kind[i] === 4 && texto.indexOf(DATA.tiles.chars[i]) >= 0)
          conMeta = true;
      if (!conMeta) return "este nivel no tiene meta: no se puede terminar";
      return "";
    }

    /* ------------------------------------------------- tamano del nivel */

    editor.redimensionar = function (dAncho, dAlto) {
      var w = ancho() + dAncho, h = alto() + dAlto;
      if (w < 20 || h < 14 || w > 512 || h > 256) return;
      guardarHistorial();
      var nuevas = filas().map(function (fila) {
        return dAncho >= 0 ? fila + Array(dAncho + 1).join(".")
                           : fila.substring(0, w);
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
      editor.filas[editor.nivel] = nuevas;
      limitarCamara();
      alCambiar();
    };

    /* --------------------------------------------------------- camara */

    function limitarCamara() {
      var maxX = Math.max(0, ancho() * TILE - canvas.width);
      var maxY = Math.max(0, alto() * TILE - (canvas.height - MINI_ALTO));
      editor.camX = Math.max(0, Math.min(editor.camX, maxX));
      editor.camY = Math.max(0, Math.min(editor.camY, maxY));
    }

    editor.mover = function (dx, dy) {
      editor.camX += dx;
      editor.camY += dy;
      limitarCamara();
    };

    editor.irA = function (px) {
      editor.camX = px - canvas.width / 2;
      limitarCamara();
    };

    /* --------------------------------------------------------- dibujado */

    function dibujarCapas() {
      var capas = DATA.levels[editor.nivel].layers || [];
      for (var n = 0; n < capas.length; n++) {
        var L = DATA.layers[capas[n]];
        var scrollX = (editor.camX * L.speed_x) >> 8;
        var col0 = scrollX >> 4, offX = scrollX & 15;
        for (var i = 0; i <= 20; i++) {
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
      var col0 = editor.camX >> 4, row0 = editor.camY >> 4;
      var offX = editor.camX & 15, offY = editor.camY & 15;
      var visiblesY = Math.ceil((canvas.height - MINI_ALTO) / 16) + 1;
      for (var c = 0; c <= 20; c++) {
        for (var r = 0; r <= visiblesY; r++) {
          var tx = col0 + c, ty = row0 + r;
          if (tx < 0 || tx >= ancho() || ty < 0 || ty >= alto()) continue;
          var ch = filas()[ty][tx];
          var x = c * 16 - offX, y = r * 16 - offY;
          if (ch === "P") {
            var pa = DATA.player.actor;
            dibujarFrame(pa.sheet, 0, x + Math.floor((16 - pa.frame_w) / 2),
                         y + 16 - pa.frame_h, false);
            continue;
          }
          if (esSpawn(ch)) {
            var actor = actorDe(ch);
            dibujarFrame(actor.sheet, 0, x + Math.floor((16 - actor.frame_w) / 2),
                         y + 16 - actor.frame_h, false);
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
      var offX = editor.camX & 15, offY = editor.camY & 15;
      ctx.strokeStyle = "rgba(255,255,255,0.10)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (var x = -offX; x <= canvas.width; x += 16) {
        ctx.moveTo(x + 0.5, 0);
        ctx.lineTo(x + 0.5, canvas.height - MINI_ALTO);
      }
      for (var y = -offY; y <= canvas.height - MINI_ALTO; y += 16) {
        ctx.moveTo(0, y + 0.5);
        ctx.lineTo(canvas.width, y + 0.5);
      }
      ctx.stroke();
    }

    function dibujarCursor() {
      if (editor.raton.x < 0) return;
      var x = editor.raton.x * 16 - editor.camX;
      var y = editor.raton.y * 16 - editor.camY;
      ctx.strokeStyle = "#f2b705";
      ctx.lineWidth = 1;
      ctx.strokeRect(x + 0.5, y + 0.5, 15, 15);
    }

    function dibujarMinimapa() {
      var y0 = canvas.height - MINI_ALTO;
      ctx.fillStyle = "rgba(10,10,16,0.92)";
      ctx.fillRect(0, y0, canvas.width, MINI_ALTO);
      var escala = Math.min(canvas.width / ancho(), (MINI_ALTO - 10) / alto());
      var offX = (canvas.width - ancho() * escala) / 2;
      for (var y = 0; y < alto(); y++) {
        for (var x = 0; x < ancho(); x++) {
          var ch = filas()[y][x];
          var color = null;
          if (ch === "P") color = "#f2b705";
          else if (esSpawn(ch)) color = "#c4453c";
          else {
            var indice = DATA.tiles.index[ch];
            var tipo = indice === undefined ? 0 : DATA.tiles.kind[indice];
            if (tipo === 1) color = "#7d8ea8";
            else if (tipo === 2) color = "#b0834a";
            else if (tipo === 3) color = "#e0574f";
            else if (tipo === 4) color = "#58d0e8";
          }
          if (!color) continue;
          ctx.fillStyle = color;
          ctx.fillRect(offX + x * escala, y0 + 5 + y * escala,
                       Math.max(1, escala), Math.max(1, escala));
        }
      }
      // recuadro de lo que se esta viendo
      ctx.strokeStyle = "rgba(255,255,255,0.65)";
      ctx.strokeRect(offX + (editor.camX / 16) * escala + 0.5, y0 + 5.5,
                     (canvas.width / 16) * escala,
                     ((canvas.height - MINI_ALTO) / 16) * escala);
      editor._mini = { y0: y0, escala: escala, offX: offX };
    }

    editor.dibujar = function () {
      ctx.fillStyle = DATA.levels[editor.nivel].background || "#000";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      dibujarCapas();
      dibujarMapa();
      dibujarRejilla();
      dibujarCursor();
      dibujarMinimapa();
    };

    /* ----------------------------------------------------------- raton */

    function aTile(px, py) {
      return {
        x: Math.floor((px + editor.camX) / 16),
        y: Math.floor((py + editor.camY) / 16)
      };
    }

    editor.pulsar = function (px, py, boton) {
      if (py >= canvas.height - MINI_ALTO) {          // clic en el minimapa
        var mini = editor._mini;
        if (mini) editor.irA(((px - mini.offX) / mini.escala) * 16);
        return;
      }
      editor.raton.pulsando = true;
      editor.raton.boton = boton;
      var t = aTile(px, py);
      if (editor.herramienta === "mano") {
        editor.raton.arrastrando = { px: px, py: py };
        return;
      }
      editor.pintar(t.x, t.y, boton === 2);
    };

    editor.mover_raton = function (px, py) {
      var t = aTile(px, py);
      editor.raton.x = t.x;
      editor.raton.y = t.y;
      if (!editor.raton.pulsando) return;
      if (editor.raton.arrastrando) {
        editor.mover(editor.raton.arrastrando.px - px, editor.raton.arrastrando.py - py);
        editor.raton.arrastrando = { px: px, py: py };
        return;
      }
      if (py < canvas.height - MINI_ALTO)
        editor.pintar(t.x, t.y, editor.raton.boton === 2);
    };

    editor.soltar = function () {
      editor.raton.pulsando = false;
      editor.raton.arrastrando = false;
    };

    /* ------------------------------------------- reconstruir para jugar */

    editor.aplicar = function () {
      for (var i = 0; i < DATA.levels.length; i++) reconstruir(i);
      alJugar();
    };

    function reconstruir(indice) {
      var nivel = DATA.levels[indice];
      var f = editor.filas[indice];
      var w = f[0].length, h = f.length;
      var vacio = DATA.tiles.index["."] !== undefined ? DATA.tiles.index["."] : 0;
      var celdas = [], spawns = [], salida = nivel.start;
      var pa = DATA.player.actor;
      for (var y = 0; y < h; y++) {
        for (var x = 0; x < w; x++) {
          var ch = f[y][x];
          if (ch === "P") {
            celdas.push(vacio);
            salida = [Math.max(0, x * 16 + Math.floor((16 - pa.box_w) / 2)),
                      Math.max(0, y * 16 + 16 - pa.box_h)];
            continue;
          }
          var s = nivel.spawn_chars[ch];
          if (s) {
            celdas.push(vacio);
            var actor = (s.kind === 0 ? DATA.enemies : DATA.items)[s.def].actor;
            spawns.push([Math.max(0, x * 16 + Math.floor((16 - actor.box_w) / 2)),
                         Math.max(0, y * 16 + 16 - actor.box_h), s.kind, s.def]);
            continue;
          }
          var indiceTile = DATA.tiles.index[ch];
          celdas.push(indiceTile === undefined ? vacio : indiceTile);
        }
      }
      nivel.width = w;
      nivel.height = h;
      nivel.cells = celdas;
      nivel.spawns = spawns;
      nivel.start = salida;
      nivel.rows = f.slice();
    }

    /* ------------------------------------------------ exportar el yaml */

    editor.exportarYaml = function () {
      var original = DATA.yaml || "";
      if (!original) return editor.exportarMapas();
      var lineas = original.split("\n");
      var salida = [];
      var nivel = 0;
      for (var i = 0; i < lineas.length; i++) {
        var linea = lineas[i];
        var marca = /^(\s*)(mapa|map|tilemap)\s*:\s*\|/.exec(linea);
        if (!marca || nivel >= editor.filas.length) {
          salida.push(linea);
          continue;
        }
        salida.push(linea);
        var sangriaBloque = null;
        var j = i + 1;
        while (j < lineas.length) {
          var siguiente = lineas[j];
          if (siguiente.trim() === "") {
            // una linea en blanco solo corta el bloque si lo que viene detras
            // esta a menos sangria
            var k = j + 1;
            while (k < lineas.length && lineas[k].trim() === "") k++;
            if (k >= lineas.length) break;
            var sangriaSiguiente = lineas[k].length - lineas[k].replace(/^\s*/, "").length;
            if (sangriaBloque !== null && sangriaSiguiente < sangriaBloque) break;
            j++;
            continue;
          }
          var sangria = siguiente.length - siguiente.replace(/^\s*/, "").length;
          if (sangria <= marca[1].length) break;
          if (sangriaBloque === null) sangriaBloque = sangria;
          j++;
        }
        var relleno = Array((sangriaBloque === null ? marca[1].length + 2 : sangriaBloque) + 1).join(" ");
        editor.filas[nivel].forEach(function (fila) {
          salida.push(relleno + fila);
        });
        nivel++;
        i = j - 1;
      }
      return salida.join("\n");
    };

    editor.exportarMapas = function () {
      return editor.filas.map(function (f, i) {
        return "# nivel " + (i + 1) + "\n    mapa: |\n" +
               f.map(function (fila) { return "      " + fila; }).join("\n");
      }).join("\n\n");
    };

    /* ------------------------------------------------------- paleta */

    editor.paleta = function () {
      var lista = [];
      lista.push({ char: "mano", etiqueta: "mover", tipo: "herramienta" });
      lista.push({ char: "P", etiqueta: "salida", tipo: "jugador",
                   hoja: DATA.player.actor.sheet, frame: 0 });
      DATA.tiles.chars.forEach(function (ch, i) {
        if (ch === " ") return;
        var tipos = ["vacio", "solido", "plataforma", "peligro", "meta", "decorado"];
        lista.push({ char: ch, etiqueta: tipos[DATA.tiles.kind[i]] || "tile",
                     tipo: "tile", hoja: "__tiles__", frame: DATA.tiles.gfx[i] });
      });
      var spawns = DATA.levels[editor.nivel].spawn_chars;
      Object.keys(spawns).forEach(function (ch) {
        var s = spawns[ch];
        var nombres = s.kind === 0 ? DATA.nombres.enemigos : DATA.nombres.objetos;
        var actor = (s.kind === 0 ? DATA.enemies : DATA.items)[s.def].actor;
        lista.push({ char: ch, etiqueta: nombres[s.def] || (s.kind ? "objeto" : "enemigo"),
                     tipo: s.kind ? "objeto" : "enemigo",
                     hoja: actor.sheet, frame: 0 });
      });
      return lista;
    };

    editor.cambiarNivel = function (indice) {
      if (indice < 0 || indice >= editor.filas.length) return;
      editor.nivel = indice;
      editor.camX = 0;
      editor.camY = Math.max(0, alto() * TILE - (canvas.height - MINI_ALTO));
      editor.aviso = comprobar();
      alCambiar();
    };

    editor.entrar = function () {
      editor.activo = true;
      editor.camY = Math.max(0, alto() * TILE - (canvas.height - MINI_ALTO));
      limitarCamara();
      editor.aviso = comprobar();
    };

    editor.salir = function () {
      editor.activo = false;
    };

    return editor;
  }

  var api = { crear: crear, MINI_ALTO: MINI_ALTO };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPEditor = api;
})(typeof window !== "undefined" ? window : this);
