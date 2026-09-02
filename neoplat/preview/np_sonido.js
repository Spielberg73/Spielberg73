/* np_sonido.js - compila lo que se escribe en `sonido:` a pasos del chip.
 *
 * Es el gemelo en JavaScript de tools/ngplat/sonido.py. Existe porque el
 * editor deja cambiar los efectos y la musica, y el preview tiene que sonar al
 * momento con lo que se acaba de escribir: los datos que trae DATA son los
 * pasos **ya compilados** (hercios y duracion), y de una lista de hercios no
 * se vuelve a "do4 mi4 sol4".
 *
 * Las dos versiones tienen que dar exactamente lo mismo, y hay una prueba que
 * lo comprueba comparandolas paso a paso (tests/test_sonido.py).
 *
 * Un paso es [hercios, duracion en frames, volumen 0-15, 1 si es ruido].
 */
(function (root) {
  "use strict";

  var SSG_RELOJ = 4000000;      /* el SSG del YM2610, para el color del ruido */
  var FREQ_MIN = 30.0;
  var FREQ_MAX = 8000.0;

  /* Semitonos desde do, en espanol y en ingles. */
  var NOTAS = {
    do: 0, c: 0, re: 2, d: 2, mi: 4, e: 4, fa: 5, f: 5,
    sol: 7, g: 7, la: 9, a: 9, si: 11, b: 11
  };
  var NOTA_RE = /^(do|re|mi|fa|sol|la|si|[a-g])([#b]?)(-?\d)?(?::(\d+))?$/i;

  function redondear(hz) { return Math.round(hz * 100) / 100; }

  /** La4 = 440 Hz, igual que en sonido.py. */
  function frecuenciaDeNota(semitono, octava) {
    var distancia = (octava - 4) * 12 + (semitono - 9);
    return 440.0 * Math.pow(2, distancia / 12);
  }

  function ErrorSonido(mensaje) { this.mensaje = mensaje; }

  function comprobar(hz) {
    if (hz <= 0) return 0.0;
    if (hz < FREQ_MIN || hz > FREQ_MAX)
      throw new ErrorSonido("la nota de " + hz.toFixed(1) +
                            " Hz se sale de lo que tocan estas maquinas");
    return hz;
  }

  /**
   * "do4 mi4 - sol4:2" -> pasos. '-' es silencio, '|' separa compases y no
   * suena, ':n' alarga esa nota n veces.
   */
  function notas(texto, velocidad, volumen) {
    var pasos = [];
    var trozos = String(texto === undefined || texto === null ? "" : texto)
                   .replace(/\|/g, " ").split(/\s+/);
    for (var i = 0; i < trozos.length; i++) {
      var token = trozos[i];
      if (!token) continue;
      if (token === "-" || token === "_" || token === ".") {
        pasos.push([0, velocidad, volumen, 0]);
        continue;
      }
      var m = NOTA_RE.exec(token);
      if (!m) throw new ErrorSonido("no entiendo la nota '" + token + "'");
      var semitono = NOTAS[m[1].toLowerCase()];
      if (m[2] === "#") semitono += 1;
      else if (m[2] === "b") semitono -= 1;
      var octava = m[3] === undefined || m[3] === null ? 4 : parseInt(m[3], 10);
      var hz = comprobar(frecuenciaDeNota(semitono, octava));
      pasos.push([redondear(hz), velocidad * parseInt(m[4] || "1", 10), volumen, 0]);
    }
    if (!pasos.length) throw new ErrorSonido("la secuencia de notas esta vacia");
    return pasos;
  }

  /** Frecuencia que sube o baja: saltos, disparos, monedas. */
  function barrido(desde, hasta, duracion, volumen) {
    duracion = Math.max(2, Math.min(60, duracion));
    var pasos = [];
    for (var i = 0; i < duracion; i++) {
      var hz = desde + (hasta - desde) * i / (duracion - 1);
      pasos.push([redondear(comprobar(hz)), 1, volumen, 0]);
    }
    return pasos;
  }

  /** Golpes y explosiones: el generador de ruido del chip. */
  function ruido(duracion, volumen, tono) {
    duracion = Math.max(1, Math.min(60, duracion));
    var hz = SSG_RELOJ / (16.0 * Math.max(1, tono || 16));
    return [[redondear(hz), duracion, volumen, 1]];
  }

  /**
   * Compila lo que hay en el editor. Devuelve {pasos: [...]} o
   * {error: "..."}: en el editor un error no puede tirar la pagina, tiene que
   * salir escrito debajo del campo que lo ha causado.
   */
  function compilar(fuente) {
    try {
      var volumen = fuente.volumen === undefined ? 12 : fuente.volumen;
      if (fuente.tipo === "barrido")
        return { pasos: barrido(Number(fuente.desde), Number(fuente.hasta),
                                Math.round(Number(fuente.duracion)), volumen) };
      if (fuente.tipo === "ruido")
        return { pasos: ruido(Math.round(Number(fuente.duracion)), volumen,
                              Math.round(Number(fuente.tono))) };
      if (fuente.tipo === "muestra") return { pasos: [] };
      return { pasos: notas(fuente.notas, Math.round(Number(fuente.velocidad)),
                            volumen) };
    } catch (e) {
      if (e instanceof ErrorSonido) return { pasos: [], error: e.mensaje };
      throw e;
    }
  }

  /** Las pistas de una cancion, cada una con su lista de pasos. */
  function compilarMusica(fuente) {
    var volumen = fuente.volumen === undefined ? 11 : fuente.volumen;
    var velocidad = Math.round(Number(fuente.velocidad));
    var pistas = [], error = "";
    (fuente.pistas || []).forEach(function (texto, i) {
      try {
        pistas.push(notas(texto, velocidad, volumen));
      } catch (e) {
        if (!(e instanceof ErrorSonido)) throw e;
        pistas.push([]);
        if (!error) error = "pista " + (i + 1) + ": " + e.mensaje;
      }
    });
    return { pistas: pistas, error: error };
  }

  var api = {
    notas: notas, barrido: barrido, ruido: ruido,
    compilar: compilar, compilarMusica: compilarMusica,
    FREQ_MIN: FREQ_MIN, FREQ_MAX: FREQ_MAX
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPSonido = api;
})(typeof window !== "undefined" ? window : this);
