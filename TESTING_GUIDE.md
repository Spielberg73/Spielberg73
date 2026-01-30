# 🧪 Guía de Pruebas - Unity 6

## Preparación para Testing

### Paso 1: Abrir el Proyecto
1. Abre **Unity Hub**
2. Click en **"Add"**
3. Selecciona la carpeta `Spielberg73/`
4. Selecciona **Unity 6.0** (o 2022.3+)
5. Click para abrir el proyecto

### Paso 2: Configurar Input System
Cuando Unity pregunte sobre Input System:
- ✅ Acepta el cambio
- ✅ Reinicia Unity
- ⏱️ Espera a que compile (1-2 minutos)

### Paso 3: Verificar Compilación
1. Abre la ventana **Console** (Window > General > Console)
2. Verifica que NO haya errores rojos
3. Si hay warnings amarillos, generalmente son OK
4. Si hay errores:
   - Lee `VALIDATION_REPORT.md`
   - Revisa la sección "Errores Potenciales"

---

## 🎮 TEST SUITE COMPLETA

### TEST 1: Configuración del Player ⭐ CRÍTICO

**Objetivo**: Configurar el jugador correctamente

**Pasos**:
1. En **Hierarchy**, click derecho > **Create Empty**
2. Renombrar a **"Player"**
3. Con Player seleccionado, en Inspector:
   - Add Component > **Character Controller**
     - Height: `2`
     - Radius: `0.5`
   - Add Component > **First Person Controller**
   - Add Component > **Battery System**
   - Add Component > **Interaction System**

4. Click derecho en Player > **Create Empty**
   - Renombrar a **"Camera"**
   - Position: `(0, 0.6, 0)`
   - Add Component > **Camera**
   - Tag: **"MainCamera"**

5. Click derecho en Camera > **Create Empty**
   - Renombrar a **"Flashlight"**
   - Position: `(0, -0.2, 0.5)`
   - Add Component > **Flashlight Controller**

**Verificación**:
```
Player
├─ CharacterController ✅
├─ FirstPersonController ✅
├─ BatterySystem ✅
├─ InteractionSystem ✅
└─ Camera
    ├─ Camera ✅
    └─ Flashlight
        └─ FlashlightController ✅
```

**Asignar Referencias**:
- FirstPersonController:
  - Camera Transform → Arrastra **Camera**
  - Player Camera → Arrastra **Camera** (componente Camera)
- FlashlightController:
  - Battery System → Arrastra **BatterySystem** del Player
- InteractionSystem:
  - Player Camera → Arrastra **Camera** (componente Camera)

**Resultado Esperado**: ✅ Sin errores en Console

---

### TEST 2: Movimiento Básico ⭐ CRÍTICO

**Objetivo**: Verificar que el jugador se mueve correctamente

**Pre-requisitos**:
- Crear un **Plane** (GameObject > 3D Object > Plane)
- Escalar el Plane a `(10, 1, 10)`

**Pasos**:
1. Click en **Play ▶️**
2. Presiona **W**
3. Presiona **A**
4. Presiona **S**
5. Presiona **D**
6. Mueve el **Mouse**

**Resultado Esperado**:
- ✅ El jugador se mueve hacia adelante con W
- ✅ El jugador se mueve hacia atrás con S
- ✅ El jugador se mueve a la izquierda con A
- ✅ El jugador se mueve a la derecha con D
- ✅ La cámara rota con el mouse
- ✅ El cursor está bloqueado (invisible)

**Si Falla**:
- Verifica que CharacterController esté añadido
- Verifica que la cámara esté asignada
- Presiona ESC para bloquear el cursor

---

### TEST 3: Head Bob y Efectos Visuales ⭐

**Objetivo**: Verificar efectos profesionales de cámara

**Pasos**:
1. En **Play mode**
2. Mantén presionado **W** (caminar hacia adelante)
3. Observa la cámara
4. Ahora mantén **Shift + W** (correr)
5. Observa el campo de visión (FOV)
6. Presiona **A** o **D** mientras caminas
7. Observa la inclinación de la cámara

**Resultado Esperado**:
- ✅ Al caminar: Cámara se balancea sutilmente (Head Bob)
- ✅ Al correr: Head Bob más pronunciado
- ✅ Al correr: FOV aumenta (sensación de velocidad)
- ✅ Al moverse lateralmente: Cámara se inclina ligeramente
- ✅ Al detenerse: Efectos vuelven a la normalidad suavemente

**Configuración**:
En FirstPersonController Inspector:
```
Enable Head Bob: ✅
Enable Dynamic FOV: ✅
Enable Camera Tilt: ✅
```

**Si Causa Mareos**: Desactivar Head Bob

---

### TEST 4: Sistema de Batería ⭐ CRÍTICO

**Objetivo**: Verificar que la batería funciona correctamente

**Pasos Iniciales**:
1. Verifica en **BatterySystem** Inspector:
   - Battery Enabled: ✅
   - Max Battery: `100`
   - Current Battery: `100`
   - Drain Rate: `5`

**Test de Drenaje**:
1. Click en **Play ▶️**
2. Presiona **F** (encender linterna)
3. Espera 10 segundos
4. Observa la batería en Inspector

**Resultado Esperado**:
- ✅ La batería comienza en 100%
- ✅ Baja 5% por segundo (50% después de 10s)
- ✅ La Console muestra: "Batería baja: 20%" al llegar al 20%
- ✅ La Console muestra: "¡BATERÍA CRÍTICA! 5%" al llegar al 5%
- ✅ Al llegar a 0%: Linterna se apaga automáticamente

**Test de Efectos Visuales**:
1. Configura `Current Battery = 30` en Inspector (en modo Play)
2. Presiona **F** para encender
3. Espera a que llegue a 20%
4. Observa la luz

**Resultado Esperado**:
- ✅ Al 20%: Luz se reduce (intensidad al 50%)
- ✅ Al 5%: Luz parpadea rápidamente
- ✅ Al 0%: Luz se apaga

---

### TEST 5: Linterna ⭐ CRÍTICO

**Objetivo**: Verificar encendido/apagado de linterna

**Pre-requisitos**:
- Configurar iluminación oscura:
  - Window > Rendering > Lighting
  - Environment > Ambient Color: Negro (0,0,0)
  - Eliminar Directional Light

**Pasos**:
1. Click en **Play ▶️**
2. Presiona **F**
3. Espera 1 segundo
4. Presiona **F** de nuevo

**Resultado Esperado**:
- ✅ Al presionar F: Linterna enciende suavemente
- ✅ Ilumina el área frente al jugador
- ✅ Tiene forma de cono (spotlight)
- ✅ Proyecta sombras
- ✅ Al presionar F de nuevo: Se apaga suavemente

**Configuración Recomendada**:
En FlashlightController Inspector:
```
Light Intensity: 3
Light Range: 15
Spot Angle: 60
Light Color: Amarillo cálido (255, 243, 214)
Enable Low Battery Effects: ✅
```

---

### TEST 6: Sistema de Interacción ⭐

**Objetivo**: Verificar que se pueden recoger baterías

**Setup**:
1. Crear batería de prueba:
   - GameObject > 3D Object > **Cube**
   - Renombrar a "Battery1"
   - Position: `(5, 1, 5)`
   - Add Component > **Battery Pickup**
   - En BatteryPickup:
     - Battery Amount: `25`
     - Rotate Object: ✅
     - Bob Up Down: ✅

**Pasos**:
1. Click en **Play ▶️**
2. Presiona **F** para encender linterna
3. Camina hacia la batería (WASD)
4. Mira directamente a la batería
5. Presiona **E** cuando aparezca el mensaje

**Resultado Esperado**:
- ✅ La batería rota automáticamente
- ✅ La batería flota arriba/abajo
- ✅ Al mirarla aparece: "[E] Recoger batería (+25%)"
- ✅ Al presionar E: Batería desaparece
- ✅ Nivel de batería aumenta +25%
- ✅ En Console: "Batería recargada: +25%. Total: X%"

**Si no funciona**:
- Verifica que InteractionSystem esté en Player
- Verifica que la cámara esté asignada en InteractionSystem
- Verifica que la batería tenga un Collider

---

### TEST 7: Gamepad/Mando 🎮 (Opcional)

**Objetivo**: Verificar controles con gamepad

**Pre-requisitos**:
- Conectar gamepad ANTES de abrir Unity
- Verificar en: Window > Analysis > Input Debugger

**Pasos**:
1. Click en **Play ▶️**
2. Usar **Stick Izquierdo** para mover
3. Usar **Stick Derecho** para mirar
4. Presionar **Botón A** para saltar
5. Mantener **L3** (click stick izq) para correr
6. Presionar **Botón X** para linterna
7. Presionar **Botón B** para interactuar

**Resultado Esperado**:
- ✅ Controles funcionan igual que teclado/mouse
- ✅ El juego detecta automáticamente el gamepad
- ✅ Sensibilidad del stick es adecuada

**Ajustar Sensibilidad**:
En FirstPersonController Inspector:
```
Gamepad Sensitivity: 3 (ajustar al gusto)
```

---

### TEST 8: UI de Batería 🎨 (Opcional)

**Objetivo**: Mostrar indicador visual de batería

**Setup**:
1. Click derecho en Hierarchy > **UI > Canvas**
2. En Canvas, click derecho > **UI > Slider**
   - Renombrar a "BatterySlider"
   - Anchor: Top-Left
   - Position: `(150, -30, 0)`
   - Width: `200`, Height: `20`

3. En Canvas, click derecho > **UI > Text - TextMeshPro**
   - Renombrar a "BatteryText"
   - Position: `(260, -30, 0)`
   - Text: "100%"

4. En Canvas, Add Component > **Battery UI**
5. Asignar referencias:
   - Battery System → Player/BatterySystem
   - Battery Slider → BatterySlider
   - Battery Text → BatteryText

**Resultado Esperado**:
- ✅ Se ve una barra en la esquina superior izquierda
- ✅ Muestra "100%" al inicio
- ✅ Barra disminuye mientras linterna está encendida
- ✅ Color cambia: Verde → Amarillo → Naranja → Rojo
- ✅ Parpadea cuando está crítica

---

## 📊 Checklist Final

Antes de dar por válido el proyecto, verificar:

### Funcionalidad Básica
- [ ] ✅ Jugador se mueve con WASD
- [ ] ✅ Cámara rota con mouse
- [ ] ✅ Jugador puede saltar
- [ ] ✅ Jugador puede correr (Shift)

### Efectos Visuales
- [ ] ✅ Head Bob funciona
- [ ] ✅ FOV dinámico al correr
- [ ] ✅ Inclinación de cámara

### Sistema de Batería
- [ ] ✅ Batería se drena al usar linterna
- [ ] ✅ Advertencias de batería baja
- [ ] ✅ Luz parpadea en batería crítica
- [ ] ✅ Se apaga automáticamente sin batería

### Sistema de Interacción
- [ ] ✅ Se pueden recoger baterías
- [ ] ✅ Mensaje de interacción aparece
- [ ] ✅ Nivel de batería aumenta

### Gamepad (si tienes)
- [ ] ✅ Controles funcionan con gamepad
- [ ] ✅ Sensibilidad adecuada

### UI (si configuraste)
- [ ] ✅ Barra de batería visible
- [ ] ✅ Porcentaje se actualiza
- [ ] ✅ Colores cambian correctamente

---

## 🐛 Troubleshooting Común

### Problema 1: Errores de Compilación
**Síntoma**: Console llena de errores rojos
**Solución**:
```
1. Assets > PlayerInputActions.inputactions > Reimport
2. Edit > Project Settings > Player
3. Active Input Handling > Input System Package (New)
4. Restart Unity
```

### Problema 2: Input no funciona
**Síntoma**: WASD/Mouse no mueven al jugador
**Solución**:
- Verificar que CharacterController esté añadido
- Verificar que cameraTransform esté asignada
- Click en ventana de Game para que reciba input
- Presionar ESC para bloquear cursor

### Problema 3: NullReferenceException
**Síntoma**: Console muestra "NullReferenceException"
**Solución**:
- Asignar TODAS las referencias en Inspector
- FlashlightController necesita BatterySystem
- InteractionSystem necesita playerCamera
- FirstPersonController necesita cameraTransform

### Problema 4: Batería no se drena
**Síntoma**: Batería se queda en 100%
**Solución**:
1. Verificar `Battery Enabled = true`
2. Verificar que linterna esté encendida (F)
3. Ver Console por errores

### Problema 5: Gamepad no funciona
**Síntoma**: Botones del mando no responden
**Solución**:
1. Conectar ANTES de abrir Unity
2. Window > Analysis > Input Debugger
3. Verificar que aparece en la lista
4. Probar con otro gamepad

---

## 🎯 Configuraciones Recomendadas

### Para Testeo Rápido
```csharp
// BatterySystem
drainRate = 20f              // Drena rápido para testing
batteryPickupAmount = 50f    // Baterías dan mucho

// FirstPersonController
walkSpeed = 8f               // Más rápido
sprintSpeed = 12f
```

### Para Juego Final
```csharp
// BatterySystem
drainRate = 5f               // Balance normal
batteryPickupAmount = 25f

// FirstPersonController
walkSpeed = 5f
sprintSpeed = 8f
```

---

## 📝 Reportar Problemas

Si encuentras un bug:

1. **Captura de pantalla** de la Console
2. **Descripción** de lo que hiciste
3. **Configuración** (valores en Inspector)
4. **Versión de Unity** que usaste

---

**Guía creada**: 2026-01-30
**Versión del Proyecto**: 2.0
**Para Unity**: 6.0 / 2022.3 LTS
