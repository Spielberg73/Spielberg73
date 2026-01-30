# 📱 Guía de Controles Móviles - Unity 6

## Descripción
Sistema completo de controles táctiles para Android e iOS con joystick virtual, botones táctiles y control de cámara por toque.

---

## ✨ Características

### 🕹️ Joystick Virtual
- **Joystick dinámico**: Aparece donde tocas
- **Dead zone configurable**: Evita movimientos no intencionados
- **Feedback visual**: Transparencia según activación
- **Retorno automático**: Vuelve al centro al soltar

### 👆 Botones Táctiles
- **3 modos**: Press, Toggle, Tap
- **Feedback visual**: Colores y escala al presionar
- **Vibración opcional**: Haptic feedback
- **Eventos Unity**: Fácil integración

### 📸 Control de Cámara Táctil
- **Área completa**: Toca y arrastra en cualquier parte
- **Multi-touch**: Joystick y cámara simultáneos
- **Sensibilidad configurable**: X e Y independientes
- **Invertir Y**: Opción para preferencias

### ⚙️ Gestor Inteligente
- **Auto-detección**: Detecta plataforma automáticamente
- **Activable desde Inspector**: On/Off con un click
- **Ocultar en editor**: No molesta durante desarrollo
- **Debug integrado**: Info en pantalla para testing

---

## 🚀 Configuración Rápida (10 minutos)

### Paso 1: Crear Canvas para Controles

```
1. Click derecho en Hierarchy > UI > Canvas
2. Renombrar a "MobileControlsUI"
3. Canvas Scaler > UI Scale Mode: Scale With Screen Size
4. Reference Resolution: 1920 x 1080
```

### Paso 2: Crear Joystick Virtual

```
1. En MobileControlsUI, click derecho > UI > Image
2. Renombrar a "MovementJoystick"
3. Configurar:
   - Anchor: Bottom-Left
   - Position: (150, 150, 0)
   - Width/Height: 200
   - Color: Blanco semi-transparente (Alpha: 0.3)
   - Source Image: (círculo, puede ser el default)

4. Crear hijo (Image):
   - Nombre: "JoystickHandle"
   - Width/Height: 80
   - Position: (0, 0, 0)
   - Color: Blanco más opaco (Alpha: 0.7)

5. En MovementJoystick, Add Component > VirtualJoystick
6. Asignar referencias:
   - Joystick Background: MovementJoystick (este mismo objeto)
   - Joystick Handle: JoystickHandle
   - Handle Range: 50
   - Dead Zone: 0.1
   - Dynamic Joystick: ✅
```

### Paso 3: Crear Área de Control de Cámara

```
1. En MobileControlsUI, click derecho > UI > Image
2. Renombrar a "CameraControlArea"
3. Configurar:
   - Anchor: Stretch (todo)
   - Left/Right/Top/Bottom: 0
   - Color: Transparente (Alpha: 0) - Solo para detectar touch
   - Raycast Target: ✅

4. Add Component > TouchCameraController
5. Configurar:
   - Touch Sensitivity X: 2
   - Touch Sensitivity Y: 2
   - Min Vertical Angle: -80
   - Max Vertical Angle: 80
   - Invert Y: ❌ (o según preferencia)
```

### Paso 4: Crear Botones de Acción

#### Botón de Salto
```
1. En MobileControlsUI, UI > Button - TextMeshPro
2. Renombrar a "JumpButton"
3. Configurar:
   - Anchor: Bottom-Right
   - Position: (-100, 150, 0)
   - Width/Height: 80
   - Texto: "↑" o imagen de salto

4. Eliminar el component Button (normal)
5. Add Component > TouchButton
6. Configurar:
   - Button Type: Press
   - Vibration On Press: ✅
   - Button Image: (asignar la Image del botón)
   - Normal Color: Blanco
   - Pressed Color: Gris
```

#### Botón de Sprint
```
1. Duplicar JumpButton (Ctrl+D)
2. Renombrar a "SprintButton"
3. Position: (-210, 150, 0)
4. Texto: "⚡" o ícono de correr
5. TouchButton ya configurado
```

#### Botón de Linterna
```
1. Duplicar JumpButton
2. Renombrar a "FlashlightButton"
3. Configurar:
   - Anchor: Top-Right
   - Position: (-100, -100, 0)
   - Texto: "🔦" o ícono de linterna
   - Button Type: Toggle (cambia!)
   - Toggle On Color: Amarillo
```

#### Botón de Interacción
```
1. Duplicar FlashlightButton
2. Renombrar a "InteractButton"
3. Position: (-210, -100, 0)
4. Texto: "E" o ícono de mano
5. Button Type: Tap
```

### Paso 5: Configurar el Gestor

```
1. En MobileControlsUI, Add Component > MobileControlsManager
2. Configurar:
   - Enable Mobile Controls: ✅
   - Auto Detect Platform: ✅
   - Hide In Editor: ✅ (para no molest ar)
   - Mobile Controls UI: MobileControlsUI (arrastra todo el Canvas)
   - Movement Joystick: (arrastra MovementJoystick)
   - Touch Camera: (arrastra CameraControlArea)
   - Jump Button: (arrastra JumpButton)
   - Sprint Button: (arrastra SprintButton)
   - Flashlight Button: (arrastra FlashlightButton)
   - Interact Button: (arrastra InteractButton)
```

### Paso 6: Conectar con el Jugador

```
1. Selecciona el objeto Player
2. En FirstPersonController:
   - Mobile Controls: (arrastra MobileControlsManager)

3. En FlashlightController:
   - Mobile Controls: (arrastra MobileControlsManager)

4. En InteractionSystem:
   - Mobile Controls: (arrastra MobileControlsManager)
```

---

## 🎮 Controles en Móvil

### Layout Final
```
┌─────────────────────────────────────┐
│                                  🔦E│ Linterna/Interactuar
│                                     │
│                                     │
│        [Toca y arrastra]            │ Control de cámara
│        [en cualquier parte]         │
│                                     │
│                                     │
│ 🕹️                           ⚡↑ │ Joystick/Sprint/Salto
└─────────────────────────────────────┘
```

### Controles Táctiles
| Acción | Control |
|--------|---------|
| Mover | Joystick (abajo izquierda) |
| Mirar | Tocar y arrastrar en pantalla |
| Saltar | Botón ↑ (abajo derecha) |
| Correr | Botón ⚡ (mantener presionado) |
| Linterna | Botón 🔦 (arriba derecha, toggle) |
| Interactuar | Botón E (toque rápido) |

---

## ⚙️ Configuración Avanzada

### VirtualJoystick

```csharp
// En Inspector
Handle Range: 50           // Distancia máxima del handle
Dead Zone: 0.1            // Zona muerta (0-1)
Reset On Release: ✅      // Volver al centro
Dynamic Joystick: ✅      // Aparecer donde tocas

// Feedback Visual
Show Debug Info: ❌       // Solo para desarrollo
Active Color: (1, 1, 1, 0.8)    // Blanco opaco
Inactive Color: (1, 1, 1, 0.3)  // Blanco transparente
```

**Dynamic Joystick**:
- ✅ **ON**: Joystick aparece donde tocas (recomendado)
- ❌ **OFF**: Joystick fijo en posición

### TouchCameraController

```csharp
// Sensibilidad
Touch Sensitivity X: 2f    // Horizontal
Touch Sensitivity Y: 2f    // Vertical
Invert Y: ❌              // Invertir eje Y

// Límites
Min Vertical Angle: -80   // Máximo mirar abajo
Max Vertical Angle: 80    // Máximo mirar arriba

// Suavizado
Smooth Rotation: ✅
Smooth Speed: 10f
```

### TouchButton

```csharp
// Tipo de Botón
Button Type:
  - Press:  Activo mientras presionas
  - Toggle: ON/OFF con cada toque
  - Tap:    Activa una vez al tocar

// Efectos
Vibration On Press: ✅    // Vibración háptica
Press Scale: 0.9         // Escala al presionar

// Colores
Normal Color: Blanco
Pressed Color: Gris
Toggle On Color: Verde   // Solo para Toggle
```

**Uso recomendado**:
- **Press**: Sprint, Salto
- **Toggle**: Linterna, Crouch
- **Tap**: Interactuar, Disparar

### MobileControlsManager

```csharp
// Activación
Enable Mobile Controls: ✅
Auto Detect Platform: ✅    // Recomendado
Hide In Editor: ✅          // No mostrar en Unity Editor

// Debug
Show Debug Info: ❌         // Info en pantalla
```

**Auto Detect Platform**:
- Detecta automáticamente Android/iOS
- En PC: Desactiva controles automáticamente
- En Editor: Respeta "Hide In Editor"

---

## 🔧 Personalización

### Cambiar Posiciones

```csharp
// Joystick
Anchor: Bottom-Left
Position: (150, 150, 0)   // Ajustar X/Y al gusto

// Botones de Acción (derecha)
Anchor: Bottom-Right
Jump: (-100, 150, 0)
Sprint: (-210, 150, 0)

// Botones Superiores
Anchor: Top-Right
Flashlight: (-100, -100, 0)
Interact: (-210, -100, 0)
```

### Cambiar Tamaños

```csharp
// Joystick
Background: 200x200px
Handle: 80x80px

// Botones
Botón estándar: 80x80px
Botón grande: 100x100px
Botón pequeño: 60x60px
```

### Añadir Más Botones

```csharp
1. Duplicar cualquier botón existente
2. Cambiar Position y Texto
3. Configurar TouchButton:
   - Button Type según necesidad
   - Colores personalizados
4. En MobileControlsManager:
   - Añadir referencia del nuevo botón
   - Crear propiedad pública para el input
   - Conectar en ConnectButtonEvents()
5. En script del jugador:
   - Leer el input con GetMiNuevoBotonInput()
```

---

## 📱 Build para Móvil

### Android

```
1. File > Build Settings
2. Plataforma: Android
3. Switch Platform
4. Player Settings:
   - Company Name: Tu nombre
   - Product Name: Nombre del juego
   - Package Name: com.tunombre.tujuego
   - Minimum API Level: Android 5.0 (API 21)
   - Target API Level: Highest installed

5. Other Settings:
   - Graphics APIs: OpenGLES3 (o Vulkan)
   - Scripting Backend: IL2CPP (recomendado)
   - Target Architectures:
     ✅ ARM64
     ✅ ARMv7

6. Build!
```

### iOS

```
1. File > Build Settings
2. Plataforma: iOS
3. Switch Platform
4. Player Settings:
   - Company Name: Tu nombre
   - Product Name: Nombre del juego
   - Bundle Identifier: com.tunombre.tujuego
   - Target minimum iOS Version: 13.0

5. Other Settings:
   - Graphics APIs: Metal
   - Architecture: ARM64
   - Target SDK: Device SDK

6. Build (generará proyecto Xcode)
7. Abrir en Xcode y compilar
```

### Optimizaciones para Móvil

```csharp
// En FirstPersonController
enableHeadBob = false        // Puede causar mareos
enableDynamicFOV = false     // Ahorra rendimiento

// En FlashlightController
flashlight.shadows = LightShadows.None  // Mucho más rápido

// En BatterySystem
updateInterval = 0.2f        // Actualizar menos frecuentemente

// En Quality Settings
Quality Settings > Shadows: No Shadows (o Soft)
Quality Settings > Anti Aliasing: 2x (o None)
Quality Settings > Texture Quality: Medium
```

---

## 🐛 Solución de Problemas

### Problema 1: Controles no aparecen en móvil
**Síntoma**: Los controles no se ven en el dispositivo

**Soluciones**:
```
1. MobileControlsManager > Enable Mobile Controls: ✅
2. MobileControlsManager > Auto Detect Platform: ✅
3. Verificar que MobileControlsUI esté activo en Hierarchy
4. En Build: Verificar que la plataforma sea Android/iOS
```

### Problema 2: Joystick no responde
**Síntoma**: Tocar el joystick no hace nada

**Soluciones**:
```
1. Verificar que VirtualJoystick tenga Image component
2. Image > Raycast Target: ✅
3. Canvas > Graphic Raycaster: Debe existir
4. EventSystem en la escena: Debe existir
5. Verificar referencias en VirtualJoystick Inspector
```

### Problema 3: Cámara no rota
**Síntoma**: Tocar y arrastrar no rota la cámara

**Soluciones**:
```
1. CameraControlArea > Image > Raycast Target: ✅
2. TouchCameraController asignado correctamente
3. FirstPersonController > Mobile Controls: Asignado
4. Verificar que no haya otro objeto bloqueando
```

### Problema 4: Botones no responden
**Síntoma**: Tocar botones no hace nada

**Soluciones**:
```
1. Verificar que TouchButton esté añadido
2. Verificar que NO esté el component Button normal
3. Button Image: Asignar la Image del botón
4. MobileControlsManager: Asignar referencia del botón
5. Verificar eventos conectados en ConnectButtonEvents()
```

### Problema 5: Controles visibles en PC
**Síntoma**: Los controles aparecen en PC/Editor

**Soluciones**:
```
1. MobileControlsManager > Hide In Editor: ✅
2. MobileControlsManager > Auto Detect Platform: ✅
3. Si quieres probar en PC:
   - Enable Mobile Controls: ✅
   - Auto Detect Platform: ❌
```

### Problema 6: Rendimiento bajo en móvil
**Síntoma**: FPS bajos, lag

**Soluciones**:
```
1. Desactivar sombras de la linterna
2. Desactivar Head Bob y FOV dinámico
3. Reducir calidad gráfica en Player Settings
4. Usar IL2CPP en vez de Mono
5. Reducir resolución de texturas
6. Quality Settings > Anti Aliasing: None o 2x
```

---

## 🎨 Mejoras Visuales (Opcional)

### Usar Sprites Personalizados

```
1. Importar sprites (PNG con transparencia)
2. Texture Type: Sprite (2D and UI)
3. En botones:
   - Image > Source Image: Tu sprite
   - Image Type: Simple
   - Preserve Aspect: ✅
```

### Añadir Efectos de Glow

```
1. Instalar URP (Universal Render Pipeline)
2. En botones, añadir componente Outline o Shadow
3. Configurar:
   - Effect Color: Blanco o color del botón
   - Effect Distance: (2, -2)
```

### Animaciones de Botones

```
1. En TouchButton, ajustar:
   - Press Scale: 0.85  // Más notorio
   - Colores más contrastados
2. Opcional: Añadir Animator con estados
```

---

## 📊 Checklist Final

### Antes de Hacer Build

- [ ] Controles probados en Unity Editor (con Enable Mobile Controls ON)
- [ ] Todas las referencias asignadas en Inspector
- [ ] MobileControlsManager configurado correctamente
- [ ] Botones funcionan (ver eventos en Debug)
- [ ] Joystick responde
- [ ] Cámara rota correctamente
- [ ] Player Settings configurados para móvil
- [ ] Optimizaciones aplicadas
- [ ] Íconos del juego añadidos
- [ ] Splash Screen configurado

### Después del Build

- [ ] Instalar en dispositivo de prueba
- [ ] Probar todos los controles
- [ ] Verificar rendimiento (FPS)
- [ ] Verificar que UI sea visible (no cortada)
- [ ] Probar rotación de pantalla (si aplicable)
- [ ] Verificar vibración (si habilitada)
- [ ] Probar en diferentes resoluciones

---

## 💡 Tips Profesionales

### 1. Zona Muerta (Dead Zone)
```
Dead Zone recomendada: 0.1 - 0.15
- Muy baja (0.05): Muy sensible, movimientos no intencionados
- Recomendada (0.1): Balance perfecto
- Alta (0.2): Necesitas mover más para activar
```

### 2. Sensibilidad de Cámara
```
Para móvil:
Touch Sensitivity X: 2.0 - 3.0
Touch Sensitivity Y: 2.0 - 3.0

Usuarios prefieren:
- Sensibilidad X ligeramente mayor que Y
- Opción de ajuste en settings
```

### 3. Tamaño de Botones
```
Mínimo recomendado: 60x60px
Óptimo: 80x80px
Grande: 100x100px

Espaciado entre botones: 20-30px
```

### 4. Posicionamiento
```
Joystick: Abajo izquierda
Acciones principales: Abajo derecha
Acciones secundarias: Arriba derecha
Nunca poner controles: Centro (tapa la vista)
```

### 5. Feedback Visual
```
Usa transparencia:
- Inactivo: Alpha 0.3 - 0.4
- Activo: Alpha 0.7 - 0.9

Usa colores:
- Normal: Blanco/Gris claro
- Activo: Verde/Azul
- Peligro: Rojo/Naranja
```

---

## 🎯 Ejemplos de Uso

### Modo Portrait (Vertical)
```
Joystick más centrado:
Position: (200, 200, 0)

Botones en fila:
Jump: (-120, 200, 0)
Sprint: (-240, 200, 0)
```

### Modo Landscape (Horizontal)
```
Configuración por defecto ya optimizada para landscape
```

### Juego de Terror
```
- Joystick muy transparente (Alpha: 0.2)
- Botones mínimos
- Sin vibración
- Color oscuro (gris oscuro)
```

### Juego de Acción
```
- Botones grandes (100x100)
- Colores brillantes
- Vibración ON
- Feedback visual intenso
```

---

**Versión**: 1.0
**Última actualización**: 2026-01-30
**Plataformas**: Android, iOS
**Unity**: 6.0 / 2022.3 LTS

---

¡Disfruta creando juegos para móvil! 📱🎮
