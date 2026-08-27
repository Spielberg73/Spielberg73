/* np_pixel.js - el editor de dibujos de NeoPlat.
 *
 * Dibuja cualquier cosa del proyecto sin salir del navegador y sin ningun
 * programa aparte: el jugador, los enemigos, los objetos, el escenario y las
 * capas de fondo. Trabaja con las mismas reglas que las maquinas:
 *
 *   - una paleta de 15 colores mas el transparente (el indice 0)
 *   - fotogramas del tamano que use el dibujo (16x16, 16x32, 32x32...),
 *     repartidos en filas de `porFila`, como en el PNG del proyecto
 *
 * El dibujo se guarda como una rejilla de indices de paleta, asi que **toda la
 * logica se puede probar sin navegador** (tests/editor.js lo hace); solo el
 * volcado a PNG y la carga desde un PNG necesitan un canvas.
 *
 * Lo que sabe hacer, aparte de pintar pixeles sueltos: linea, rectangulo y
 * elipse (huecos o rellenos), relleno por zonas, seleccionar un trozo para
 * moverlo o copiarlo, espejo en los dos ejes, girar, desplazar con vuelta,
 * cambiar un color por otro en todo el dibujo, y anadir, quitar, mover o
 * duplicar fotogramas. Todo pasa por `empezarCambio()`, asi que todo se
 * deshace.
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

  var MAX_DESHACER = 64;

  function aRgb(hex) {
    var t = String(hex || "#000000").replace("#", "");
    return [parseInt(t.substr(0, 2), 16) || 0,
            parseInt(t.substr(2, 2), 16) || 0,
            parseInt(t.substr(4, 2), 16) || 0];
  }

  /* Que color de `paleta` se parece mas a `hex`. Devuelve el indice tal como lo
     usan los pixeles (1 a 15; el 0 es el transparente) y si es clavado o solo
     parecido, que es lo que hace falta para poder avisar al pegar entre dos
     dibujos con paletas distintas. */
  function masParecido(hex, paleta) {
    var a = aRgb(hex), mejor = 1, distancia = Infinity;
    for (var i = 0; i < paleta.length; i++) {
      var b = aRgb(paleta[i]);
      var d = (a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]) +
              (a[2] - b[2]) * (a[2] - b[2]);
      if (d < distancia) { distancia = d; mejor = i + 1; }
    }
    return { indice: mejor, exacto: distancia === 0 };
  }

  function crear(opciones) {
    opciones = opciones || {};
    var lienzo = {
      ancho: opciones.ancho || 16,
      alto: opciones.alto || 16,
      frames: Math.max(1, opciones.frames || 1),
      /* como se reparten los frames en el PNG: por defecto todos en una fila,
         que es lo que hacen las hojas del kit, pero gfx.py admite varias */
      porFila: 0,
      paleta: (opciones.paleta || PALETA_POR_DEFECTO).slice(0, 15),
      color: 1,
      herramienta: "lapiz",
      historial: [],
      rehacerPila: []
    };
    while (lienzo.paleta.length < 15) lienzo.paleta.push("#000000");
    if (!lienzo.porFila) lienzo.porFila = lienzo.frames;

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

    /* Un punto al que volver. Se guardan los pixeles **y cuantos fotogramas
       habia**: si no, deshacer un "duplicar fotograma" dejaba el lienzo
       diciendo que tiene mas de los que caben en la memoria que le queda, y a
       partir de ahi el ultimo se leia fuera del array. */
    function instantanea() {
      return { pixeles: lienzo.pixeles.slice(), frames: lienzo.frames,
               porFila: lienzo.porFila };
    }

    function volver(a) {
      lienzo.pixeles = a.pixeles;
      lienzo.frames = a.frames;
      lienzo.porFila = a.porFila;
    }

    lienzo.empezarCambio = function () {
      lienzo.historial.push(instantanea());
      if (lienzo.historial.length > MAX_DESHACER) lienzo.historial.shift();
      lienzo.rehacerPila.length = 0;
    };

    lienzo.deshacer = function () {
      var previo = lienzo.historial.pop();
      if (!previo) return false;
      lienzo.rehacerPila.push(instantanea());
      volver(previo);
      return true;
    };

    lienzo.rehacer = function () {
      var siguiente = lienzo.rehacerPila.pop();
      if (!siguiente) return false;
      lienzo.historial.push(instantanea());
      volver(siguiente);
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

    /* ------------------------------------------------ formas y seleccion */

    /* Bresenham: la linea de toda la vida, sin coma flotante ni huecos. */
    lienzo.linea = function (frame, x0, y0, x1, y1, color) {
      var dx = Math.abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
      var dy = -Math.abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
      var error = dx + dy, cambio = false;
      for (;;) {
        if (lienzo.pintar(frame, x0, y0, color)) cambio = true;
        if (x0 === x1 && y0 === y1) break;
        var doble = 2 * error;
        if (doble >= dy) { error += dy; x0 += sx; }
        if (doble <= dx) { error += dx; y0 += sy; }
      }
      return cambio;
    };

    lienzo.rect = function (frame, x0, y0, x1, y1, color, relleno) {
      var ax = Math.min(x0, x1), bx = Math.max(x0, x1);
      var ay = Math.min(y0, y1), by = Math.max(y0, y1);
      var cambio = false, x, y;
      for (y = ay; y <= by; y++) {
        for (x = ax; x <= bx; x++) {
          var borde = (x === ax || x === bx || y === ay || y === by);
          if (!relleno && !borde) continue;
          if (lienzo.pintar(frame, x, y, color)) cambio = true;
        }
      }
      return cambio;
    };

    /* Elipse por la ecuacion, mirando pixel a pixel: a estos tamanos (16, 32)
       cuesta nada y sale bien centrada tanto en pares como en impares. */
    lienzo.elipse = function (frame, x0, y0, x1, y1, color, relleno) {
      var ax = Math.min(x0, x1), bx = Math.max(x0, x1);
      var ay = Math.min(y0, y1), by = Math.max(y0, y1);
      var cx = (ax + bx) / 2, cy = (ay + by) / 2;
      var rx = (bx - ax) / 2 + 0.5, ry = (by - ay) / 2 + 0.5;
      var cambio = false, x, y;
      for (y = ay; y <= by; y++) {
        for (x = ax; x <= bx; x++) {
          var dx = (x + 0.5 - cx - 0.5) / rx, dy = (y + 0.5 - cy - 0.5) / ry;
          var d = dx * dx + dy * dy;
          if (d > 1) continue;
          if (!relleno) {
            /* el borde: dentro pero con algun vecino fuera */
            var dentroVecinos = true;
            var vecinos = [[1, 0], [-1, 0], [0, 1], [0, -1]];
            for (var v = 0; v < vecinos.length; v++) {
              var vx = (x + vecinos[v][0] + 0.5 - cx - 0.5) / rx;
              var vy = (y + vecinos[v][1] + 0.5 - cy - 0.5) / ry;
              if (vx * vx + vy * vy > 1) { dentroVecinos = false; break; }
            }
            if (dentroVecinos) continue;
          }
          if (lienzo.pintar(frame, x, y, color)) cambio = true;
        }
      }
      return cambio;
    };

    /* Un trozo suelto del dibujo, para moverlo o copiarlo. */
    lienzo.recortar = function (frame, x0, y0, x1, y1) {
      var ax = Math.max(0, Math.min(x0, x1)), bx = Math.min(lienzo.ancho - 1, Math.max(x0, x1));
      var ay = Math.max(0, Math.min(y0, y1)), by = Math.min(lienzo.alto - 1, Math.max(y0, y1));
      var ancho = bx - ax + 1, alto = by - ay + 1;
      var trozo = { ancho: ancho, alto: alto, pixeles: new Uint8Array(ancho * alto) };
      for (var y = 0; y < alto; y++) {
        for (var x = 0; x < ancho; x++) {
          trozo.pixeles[y * ancho + x] = lienzo.coger(frame, ax + x, ay + y);
        }
      }
      return trozo;
    };

    /* Pega un trozo. `conTransparente` decide si el hueco del trozo borra lo
       que hay debajo (mover) o lo respeta (sello). */
    lienzo.pegar = function (frame, trozo, x0, y0, conTransparente) {
      var cambio = false;
      for (var y = 0; y < trozo.alto; y++) {
        for (var x = 0; x < trozo.ancho; x++) {
          var valor = trozo.pixeles[y * trozo.ancho + x];
          if (!valor && !conTransparente) continue;
          if (lienzo.pintar(frame, x0 + x, y0 + y, valor)) cambio = true;
        }
      }
      return cambio;
    };

    /* Pega un trozo que viene de **otro dibujo**, que tendra otra paleta.
     *
     * Los pixeles son indices, no colores: pegarlos tal cual cambiaria los
     * colores del dibujo sin avisar. Asi que se traduce color a color, se usa
     * el clavado si esta y el mas parecido si no, y se devuelve cuantos han
     * tenido que aproximarse para poder decirlo. Es la misma cuenta que hace
     * el compilador cuando un dibujo no cabe en la paleta de la maquina.
     */
    lienzo.pegarDeOtro = function (frame, trozo, paletaOrigen, x0, y0,
                                   conTransparente) {
      var mapa = [0], aproximados = 0, i;
      paletaOrigen = paletaOrigen || lienzo.paleta;
      for (i = 0; i < paletaOrigen.length; i++) {
        var cerca = masParecido(paletaOrigen[i], lienzo.paleta);
        if (!cerca.exacto) aproximados++;
        mapa.push(cerca.indice);
      }
      var traducido = { ancho: trozo.ancho, alto: trozo.alto,
                        pixeles: new Uint8Array(trozo.pixeles.length) };
      var usados = {};
      for (i = 0; i < trozo.pixeles.length; i++) {
        var valor = trozo.pixeles[i];
        traducido.pixeles[i] = valor ? (mapa[valor] || 1) : 0;
        if (valor) usados[valor] = 1;
      }
      /* solo cuentan los colores que de verdad aparecen en el trozo */
      aproximados = 0;
      Object.keys(usados).forEach(function (clave) {
        var n = Number(clave);
        if (n && paletaOrigen[n - 1] &&
            !masParecido(paletaOrigen[n - 1], lienzo.paleta).exacto) aproximados++;
      });
      return { cambio: lienzo.pegar(frame, traducido, x0, y0, conTransparente),
               aproximados: aproximados };
    };

    lienzo.borrarZona = function (frame, x0, y0, x1, y1) {
      return lienzo.rect(frame, x0, y0, x1, y1, 0, true);
    };

    /* ----------------------------------------------------- el frame entero */

    lienzo.frameEntero = function (frame) {
      return lienzo.recortar(frame, 0, 0, lienzo.ancho - 1, lienzo.alto - 1);
    };

    lienzo.espejoV = function (frame) {
      for (var x = 0; x < lienzo.ancho; x++) {
        for (var y = 0; y < Math.floor(lienzo.alto / 2); y++) {
          var a = indice(frame, x, y);
          var b = indice(frame, x, lienzo.alto - 1 - y);
          var tmp = lienzo.pixeles[a];
          lienzo.pixeles[a] = lienzo.pixeles[b];
          lienzo.pixeles[b] = tmp;
        }
      }
    };

    /* Gira noventa grados a la derecha. Solo tiene sentido si es cuadrado; si
       no lo es, devuelve false y no toca nada. */
    lienzo.rotar = function (frame) {
      if (lienzo.ancho !== lienzo.alto) return false;
      var n = lienzo.ancho;
      var copia = lienzo.pixeles.slice(frame * tamanoFrame(),
                                       (frame + 1) * tamanoFrame());
      for (var y = 0; y < n; y++) {
        for (var x = 0; x < n; x++) {
          lienzo.pixeles[indice(frame, x, y)] = copia[(n - 1 - x) * n + y];
        }
      }
      return true;
    };

    /* Desplaza dando la vuelta: util para centrar un dibujo sin redibujarlo. */
    lienzo.desplazar = function (frame, dx, dy) {
      var copia = lienzo.pixeles.slice(frame * tamanoFrame(),
                                       (frame + 1) * tamanoFrame());
      for (var y = 0; y < lienzo.alto; y++) {
        for (var x = 0; x < lienzo.ancho; x++) {
          var ox = ((x - dx) % lienzo.ancho + lienzo.ancho) % lienzo.ancho;
          var oy = ((y - dy) % lienzo.alto + lienzo.alto) % lienzo.alto;
          lienzo.pixeles[indice(frame, x, y)] = copia[oy * lienzo.ancho + ox];
        }
      }
    };

    /* Cambia un color por otro en todo el dibujo (o solo en un frame). */
    lienzo.cambiarColor = function (viejo, nuevo, frame) {
      var desde = frame === undefined ? 0 : frame * tamanoFrame();
      var hasta = frame === undefined ? lienzo.pixeles.length : desde + tamanoFrame();
      var cambio = false;
      for (var i = desde; i < hasta; i++) {
        if (lienzo.pixeles[i] === viejo) { lienzo.pixeles[i] = nuevo; cambio = true; }
      }
      return cambio;
    };

    /* --------------------------------------------------------- fotogramas */

    lienzo.intercambiarFrames = function (a, b) {
      if (a === b || a < 0 || b < 0 || a >= lienzo.frames || b >= lienzo.frames) return false;
      var tam = tamanoFrame();
      var copia = lienzo.pixeles.slice(a * tam, (a + 1) * tam);
      lienzo.pixeles.copyWithin(a * tam, b * tam, (b + 1) * tam);
      lienzo.pixeles.set(copia, b * tam);
      return true;
    };

    lienzo.insertarFrame = function (donde, duplicar) {
      if (lienzo.frames >= 16) return false;
      var tam = tamanoFrame();
      var nuevos = new Uint8Array(tam * (lienzo.frames + 1));
      nuevos.set(lienzo.pixeles.subarray(0, donde * tam), 0);
      if (duplicar && donde > 0) {
        nuevos.set(lienzo.pixeles.subarray((donde - 1) * tam, donde * tam), donde * tam);
      }
      nuevos.set(lienzo.pixeles.subarray(donde * tam), (donde + 1) * tam);
      lienzo.pixeles = nuevos;
      lienzo.frames++;
      if (lienzo.porFila < lienzo.frames) lienzo.porFila = lienzo.frames;
      return true;
    };

    lienzo.borrarFrame = function (donde) {
      if (lienzo.frames <= 1) return false;
      var tam = tamanoFrame();
      var nuevos = new Uint8Array(tam * (lienzo.frames - 1));
      nuevos.set(lienzo.pixeles.subarray(0, donde * tam), 0);
      nuevos.set(lienzo.pixeles.subarray((donde + 1) * tam), donde * tam);
      lienzo.pixeles = nuevos;
      lienzo.frames--;
      if (lienzo.porFila > lienzo.frames) lienzo.porFila = lienzo.frames;
      return true;
    };

    /* Que indices de paleta se usan de verdad, en orden. Con esto el editor
       puede decirte cuantos colores llevas y cuales sobran. */
    lienzo.indicesUsados = function () {
      var vistos = {}, salida = [];
      for (var i = 0; i < lienzo.pixeles.length; i++) {
        var v = lienzo.pixeles[i];
        if (v && !vistos[v]) { vistos[v] = 1; salida.push(v); }
      }
      return salida.sort(function (a, b) { return a - b; });
    };

    /* ------------------------------------------------------- a imagen */

    function componentes(color) {
      var texto = String(color).replace("#", "");
      return [parseInt(texto.substr(0, 2), 16),
              parseInt(texto.substr(2, 2), 16),
              parseInt(texto.substr(4, 2), 16)];
    }

    /* Donde cae cada frame dentro del PNG. Las hojas del kit suelen llevarlos
       todos en una fila, pero gfx.py admite varias y hay que respetarlo o al
       guardar se descolocarian. */
    lienzo.filas = function () {
      return Math.ceil(lienzo.frames / lienzo.porFila);
    };

    lienzo.anchoHoja = function () { return lienzo.ancho * lienzo.porFila; };
    lienzo.altoHoja = function () { return lienzo.alto * lienzo.filas(); };

    function sitioDeFrame(f) {
      return [(f % lienzo.porFila) * lienzo.ancho,
              Math.floor(f / lienzo.porFila) * lienzo.alto];
    }

    /** Vuelca la hoja completa sobre un canvas, con su reparto de filas. */
    lienzo.aCanvas = function (canvas) {
      canvas.width = lienzo.anchoHoja();
      canvas.height = lienzo.altoHoja();
      var ctx = canvas.getContext("2d");
      var imagen = ctx.createImageData(canvas.width, canvas.height);
      for (var f = 0; f < lienzo.frames; f++) {
        var sitio = sitioDeFrame(f);
        for (var y = 0; y < lienzo.alto; y++) {
          for (var x = 0; x < lienzo.ancho; x++) {
            var color = lienzo.coger(f, x, y);
            var destino = ((sitio[1] + y) * canvas.width + sitio[0] + x) * 4;
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

    /** Carga un dibujo existente (se queda con los 15 colores mas usados). */
    lienzo.desdeImagen = function (imagen, documento) {
      var canvas = documento.createElement("canvas");
      canvas.width = lienzo.anchoHoja();
      canvas.height = lienzo.altoHoja();
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
    if (!lienzo.porFila) lienzo.porFila = lienzo.frames;

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
        var columna = Math.floor(x / lienzo.ancho);
        var fila = Math.floor(y / lienzo.alto);
        var frame = fila * lienzo.porFila + columna;
        var destino = frame * tamanoFrame()
                    + (y % lienzo.alto) * lienzo.ancho + (x % lienzo.ancho);
        if (frame >= lienzo.frames || destino >= lienzo.pixeles.length) continue;
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

  var api = { crear: crear, PALETA: PALETA_POR_DEFECTO,
              masParecido: masParecido };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPPixel = api;
})(typeof window !== "undefined" ? window : this);
