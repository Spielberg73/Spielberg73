/* np_pixel.js - editor de dibujos (sprites) dentro del editor de NeoPlat.
 *
 * Sirve para dibujar enemigos y objetos nuevos sin salir del navegador y sin
 * ningun programa aparte. Trabaja con las mismas reglas que la Neo Geo:
 *
 *   - una paleta de 15 colores mas el transparente (el indice 0)
 *   - fotogramas del tamano que use el actor (16x16, 16x32, 32x32...)
 *
 * El dibujo se guarda como una rejilla de indices de paleta, asi que la logica
 * se puede probar sin navegador; solo el volcado a PNG necesita un canvas.
 */
(function (root) {
  "use strict";

  /* Paleta de partida: colores que quedan bien en pixel art y caben en la
     Neo Geo (se puede cambiar cualquiera). */
  var PALETA_POR_DEFECTO = [
    "#181018", "#f8f8f8", "#a8a8b8", "#585868",
    "#f85858", "#a82820", "#f8a038", "#f8d848",
    "#58b848", "#207838", "#48b8f8", "#2058c8",
    "#c058f8", "#f8b8a0"
  ];

  function crear(opciones) {
    opciones = opciones || {};
    var lienzo = {
      ancho: opciones.ancho || 16,
      alto: opciones.alto || 16,
      frames: Math.max(1, opciones.frames || 1),
      paleta: (opciones.paleta || PALETA_POR_DEFECTO).slice(0, 15),
      color: 1,
      herramienta: "lapiz",
      historial: [],
      rehacerPila: []
    };
    while (lienzo.paleta.length < 15) lienzo.paleta.push("#000000");

    function tamanoFrame() { return lienzo.ancho * lienzo.alto; }

    lienzo.pixeles = new Uint8Array(tamanoFrame() * lienzo.frames);

    function indice(frame, x, y) {
      return frame * tamanoFrame() + y * lienzo.ancho + x;
    }

    lienzo.dentro = function (x, y) {
      return x >= 0 && y >= 0 && x < lienzo.ancho && y < lienzo.alto;
    };

    lienzo.coger = function (frame, x, y) {
      if (!lienzo.dentro(x, y)) return 0;
      return lienzo.pixeles[indice(frame, x, y)];
    };

    lienzo.empezarCambio = function () {
      lienzo.historial.push(lienzo.pixeles.slice());
      if (lienzo.historial.length > 40) lienzo.historial.shift();
      lienzo.rehacerPila.length = 0;
    };

    lienzo.deshacer = function () {
      var previo = lienzo.historial.pop();
      if (!previo) return false;
      lienzo.rehacerPila.push(lienzo.pixeles.slice());
      lienzo.pixeles = previo;
      return true;
    };

    lienzo.rehacer = function () {
      var siguiente = lienzo.rehacerPila.pop();
      if (!siguiente) return false;
      lienzo.historial.push(lienzo.pixeles.slice());
      lienzo.pixeles = siguiente;
      return true;
    };

    lienzo.pintar = function (frame, x, y, color) {
      if (!lienzo.dentro(x, y)) return false;
      var pos = indice(frame, x, y);
      if (lienzo.pixeles[pos] === color) return false;
      lienzo.pixeles[pos] = color;
      return true;
    };

    lienzo.relleno = function (frame, x, y, color) {
      if (!lienzo.dentro(x, y)) return false;
      var objetivo = lienzo.coger(frame, x, y);
      if (objetivo === color) return false;
      var pila = [[x, y]];
      while (pila.length) {
        var punto = pila.pop();
        var px = punto[0], py = punto[1];
        if (!lienzo.dentro(px, py)) continue;
        if (lienzo.coger(frame, px, py) !== objetivo) continue;
        lienzo.pixeles[indice(frame, px, py)] = color;
        pila.push([px + 1, py], [px - 1, py], [px, py + 1], [px, py - 1]);
      }
      return true;
    };

    lienzo.limpiarFrame = function (frame) {
      for (var i = 0; i < tamanoFrame(); i++) lienzo.pixeles[frame * tamanoFrame() + i] = 0;
    };

    lienzo.copiarFrame = function (desde, hasta) {
      for (var i = 0; i < tamanoFrame(); i++) {
        lienzo.pixeles[hasta * tamanoFrame() + i] = lienzo.pixeles[desde * tamanoFrame() + i];
      }
    };

    lienzo.espejo = function (frame) {
      for (var y = 0; y < lienzo.alto; y++) {
        for (var x = 0; x < Math.floor(lienzo.ancho / 2); x++) {
          var a = indice(frame, x, y);
          var b = indice(frame, lienzo.ancho - 1 - x, y);
          var tmp = lienzo.pixeles[a];
          lienzo.pixeles[a] = lienzo.pixeles[b];
          lienzo.pixeles[b] = tmp;
        }
      }
    };

    lienzo.ponerFrames = function (cuantos) {
      cuantos = Math.max(1, Math.min(8, cuantos));
      var nuevos = new Uint8Array(tamanoFrame() * cuantos);
      nuevos.set(lienzo.pixeles.subarray(0, Math.min(lienzo.pixeles.length, nuevos.length)));
      lienzo.pixeles = nuevos;
      lienzo.frames = cuantos;
    };

    lienzo.vacio = function () {
      for (var i = 0; i < lienzo.pixeles.length; i++) if (lienzo.pixeles[i]) return false;
      return true;
    };

    lienzo.coloresUsados = function () {
      var vistos = {};
      for (var i = 0; i < lienzo.pixeles.length; i++) {
        if (lienzo.pixeles[i]) vistos[lienzo.pixeles[i]] = 1;
      }
      return Object.keys(vistos).length;
    };

    /* ------------------------------------------------------- a imagen */

    function componentes(color) {
      var texto = String(color).replace("#", "");
      return [parseInt(texto.substr(0, 2), 16),
              parseInt(texto.substr(2, 2), 16),
              parseInt(texto.substr(4, 2), 16)];
    }

    /** Vuelca la hoja completa (los frames en fila) sobre un canvas. */
    lienzo.aCanvas = function (canvas) {
      canvas.width = lienzo.ancho * lienzo.frames;
      canvas.height = lienzo.alto;
      var ctx = canvas.getContext("2d");
      var imagen = ctx.createImageData(canvas.width, canvas.height);
      for (var f = 0; f < lienzo.frames; f++) {
        for (var y = 0; y < lienzo.alto; y++) {
          for (var x = 0; x < lienzo.ancho; x++) {
            var color = lienzo.coger(f, x, y);
            var destino = (y * canvas.width + f * lienzo.ancho + x) * 4;
            if (!color) {
              imagen.data[destino + 3] = 0;
              continue;
            }
            var rgb = componentes(lienzo.paleta[color - 1] || "#ffffff");
            imagen.data[destino] = rgb[0];
            imagen.data[destino + 1] = rgb[1];
            imagen.data[destino + 2] = rgb[2];
            imagen.data[destino + 3] = 255;
          }
        }
      }
      ctx.putImageData(imagen, 0, 0);
      return canvas;
    };

    lienzo.aDataURL = function (documento) {
      var canvas = documento.createElement("canvas");
      lienzo.aCanvas(canvas);
      return canvas.toDataURL("image/png");
    };

    /** Carga un dibujo existente para partir de el (se queda con 15 colores). */
    lienzo.desdeImagen = function (imagen, documento) {
      var canvas = documento.createElement("canvas");
      canvas.width = lienzo.ancho * lienzo.frames;
      canvas.height = lienzo.alto;
      var ctx = canvas.getContext("2d");
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(imagen, 0, 0, canvas.width, canvas.height,
                    0, 0, canvas.width, canvas.height);
      var datos = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      var cuenta = {};
      var i, clave;
      for (i = 0; i < datos.length; i += 4) {
        if (datos[i + 3] < 128) continue;
        clave = datos[i] + "," + datos[i + 1] + "," + datos[i + 2];
        cuenta[clave] = (cuenta[clave] || 0) + 1;
      }
      var colores = Object.keys(cuenta).sort(function (a, b) { return cuenta[b] - cuenta[a]; })
                          .slice(0, 15);
      lienzo.paleta = colores.map(function (c) {
        var p = c.split(",");
        return "#" + p.map(function (v) {
          var h = Number(v).toString(16);
          return h.length < 2 ? "0" + h : h;
        }).join("");
      });
      while (lienzo.paleta.length < 15) lienzo.paleta.push("#000000");

      function masCercano(r, g, b) {
        var mejor = 1, distancia = Infinity;
        for (var k = 0; k < colores.length; k++) {
          var p = colores[k].split(",");
          var d = Math.pow(r - p[0], 2) + Math.pow(g - p[1], 2) + Math.pow(b - p[2], 2);
          if (d < distancia) { distancia = d; mejor = k + 1; }
        }
        return mejor;
      }

      var mapa = {};
      colores.forEach(function (c, k) { mapa[c] = k + 1; });
      for (i = 0; i < datos.length; i += 4) {
        var pos = i / 4;
        var x = pos % canvas.width, y = Math.floor(pos / canvas.width);
        var frame = Math.floor(x / lienzo.ancho);
        var destino = frame * tamanoFrame() + y * lienzo.ancho + (x % lienzo.ancho);
        if (destino >= lienzo.pixeles.length) continue;
        if (datos[i + 3] < 128) { lienzo.pixeles[destino] = 0; continue; }
        clave = datos[i] + "," + datos[i + 1] + "," + datos[i + 2];
        lienzo.pixeles[destino] = mapa[clave] || masCercano(datos[i], datos[i + 1], datos[i + 2]);
      }
      return lienzo;
    };

    /** Dibujo de ejemplo, para no empezar con el lienzo en blanco. */
    lienzo.bicho = function () {
      var w = lienzo.ancho, h = lienzo.alto;
      for (var f = 0; f < lienzo.frames; f++) {
        var salto = f % 2;
        var cx = w / 2, cy = h * 0.62 + salto;
        for (var y = 0; y < h; y++) {
          for (var x = 0; x < w; x++) {
            var dx = (x + 0.5 - cx) / (w * 0.42);
            var dy = (y + 0.5 - cy) / (h * 0.40);
            if (dx * dx + dy * dy > 1) continue;
            lienzo.pintar(f, x, y, y > cy ? 6 : 5);      // sombra en la parte baja
          }
        }
        var oy = Math.floor(h * 0.5) + salto;
        lienzo.pintar(f, Math.floor(w * 0.35), oy, 2);
        lienzo.pintar(f, Math.floor(w * 0.62), oy, 2);
        lienzo.pintar(f, Math.floor(w * 0.35), oy + 1, 1);
        lienzo.pintar(f, Math.floor(w * 0.62), oy + 1, 1);
      }
      return lienzo;
    };

    return lienzo;
  }

  var api = { crear: crear, PALETA: PALETA_POR_DEFECTO };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPPixel = api;
})(typeof window !== "undefined" ? window : this);
