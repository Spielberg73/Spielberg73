# Lista de Verificación de Pruebas

## ✅ Checklist de Funcionalidad del Juego

### Antes de Empezar
- [ ] Unity está instalado (versión 2020.3 o superior)
- [ ] El proyecto se abre sin errores en Unity
- [ ] No hay errores en la consola de Unity (Console window)

### Configuración de la Escena
- [ ] La escena `MainScene.unity` se carga correctamente
- [ ] El objeto Player está presente en la jerarquía
- [ ] El objeto Camera es hijo de Player
- [ ] El objeto Flashlight es hijo de Camera
- [ ] Hay un plano (Ground) en la escena
- [ ] Hay cubos de prueba en la escena

### Pruebas de Movimiento del Jugador
1. **Movimiento Básico**
   - [ ] Presiona W → El jugador se mueve hacia adelante
   - [ ] Presiona S → El jugador se mueve hacia atrás
   - [ ] Presiona A → El jugador se mueve a la izquierda
   - [ ] Presiona D → El jugador se mueve a la derecha
   - [ ] El movimiento es suave y sin saltos

2. **Control de Cámara**
   - [ ] Mueve el mouse a la izquierda → La cámara rota a la izquierda
   - [ ] Mueve el mouse a la derecha → La cámara rota a la derecha
   - [ ] Mueve el mouse arriba → La cámara mira hacia arriba
   - [ ] Mueve el mouse abajo → La cámara mira hacia abajo
   - [ ] La cámara tiene límite vertical (no gira 360° verticalmente)

3. **Funciones Adicionales**
   - [ ] Presiona SHIFT + W → El jugador corre más rápido
   - [ ] Presiona ESPACIO → El jugador salta
   - [ ] El jugador aterriza correctamente después de saltar
   - [ ] Presiona ESC → El cursor se libera (se puede mover fuera del juego)
   - [ ] Presiona ESC de nuevo → El cursor se bloquea de nuevo

### Pruebas de Linterna
1. **Encendido/Apagado**
   - [ ] Al iniciar el juego, la linterna está apagada
   - [ ] La escena está oscura sin la linterna
   - [ ] Presiona F → La linterna se enciende
   - [ ] La linterna ilumina el área frente al jugador
   - [ ] Presiona F de nuevo → La linterna se apaga

2. **Comportamiento de la Luz**
   - [ ] La luz de la linterna sigue el movimiento del mouse
   - [ ] La luz ilumina los objetos en su cono de visión
   - [ ] Los objetos proyectan sombras con la linterna
   - [ ] El rango de la luz es aproximadamente 15 unidades
   - [ ] El ángulo de la luz cubre un área adecuada

### Pruebas de Física
- [ ] El jugador no atraviesa el suelo
- [ ] El jugador no atraviesa los cubos
- [ ] La gravedad funciona correctamente
- [ ] El jugador puede subir pequeñas pendientes

### Pruebas de Ambiente
- [ ] La iluminación ambiental es muy oscura/negra
- [ ] Sin la linterna, apenas se ve el entorno
- [ ] Con la linterna, se puede explorar el espacio

## 🐛 Problemas Comunes y Soluciones

### El jugador cae infinitamente
**Solución:** Verifica que el objeto Ground tiene un MeshCollider o BoxCollider

### No puedo mover el mouse
**Solución:** Haz clic en la ventana del juego, luego presiona ESC para bloquear el cursor

### La linterna no enciende
**Solución:**
1. Verifica que el script FlashlightController está en el objeto Flashlight
2. Comprueba en la consola si hay errores
3. Intenta presionar F mientras estás en modo Play

### La escena está muy brillante
**Solución:**
1. Ve a Window > Rendering > Lighting
2. En Environment, cambia Ambient Color a negro (0,0,0)
3. Desactiva o elimina cualquier Directional Light

### Los scripts no se asignan
**Solución:**
1. Asegúrate de que los archivos .cs están en Assets/Scripts/
2. Espera a que Unity compile (barra de progreso en la parte inferior)
3. Si hay errores de compilación, revisa la consola

## 📊 Métricas de Rendimiento Esperadas

- FPS: 60+ en hardware moderno
- Sin lag durante el movimiento
- Respuesta inmediata al presionar teclas
- No hay stuttering al mover la cámara

## ✍️ Notas de la Prueba

Versión del proyecto: 1.0
Fecha de prueba: __________
Probado por: __________
Versión de Unity: __________

**Resultado General:**
- [ ] Todo funciona correctamente ✅
- [ ] Funciona con problemas menores ⚠️
- [ ] No funciona ❌

**Comentarios adicionales:**
_______________________________________________
_______________________________________________
_______________________________________________
