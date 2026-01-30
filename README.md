# 🔦 Juego de Linterna en Primera Persona - Unity 6

## Descripción
Proyecto profesional de Unity 6 que implementa un juego en primera persona con mecánicas avanzadas estilo Half-Life, sistema de batería, interacción con objetos y soporte completo para teclado/mouse y gamepad.

## ✨ Características Principales

### 🎮 Sistema de Control Profesional
- ✅ **Input System moderno** de Unity con soporte para múltiples dispositivos
- ✅ **Teclado + Mouse** completamente configurado
- ✅ **Gamepad/Mando** con soporte nativo (Xbox, PlayStation, etc.)
- ✅ **Cambio automático** entre esquemas de control

### 🏃 Mecánicas de Movimiento Avanzadas
- ✅ Movimiento fluido con **aceleración y deceleración** suaves
- ✅ Sistema de **sprint** con efectos visuales
- ✅ Sistema de **agacharse** (crouch) con transición suave
- ✅ **Control aéreo** reducido para realismo
- ✅ Salto con cooldown

### 📸 Efectos Visuales Profesionales (Estilo Half-Life)
- ✅ **Head Bob** - Balanceo de cámara al caminar/correr
- ✅ **FOV Dinámico** - Campo de visión aumenta al correr
- ✅ **Inclinación de Cámara** - Tilt al moverse lateralmente
- ✅ Transiciones suaves entre estados

### 🔋 Sistema de Batería Completo
- ✅ Batería que se **drena** mientras la linterna está encendida
- ✅ **Efectos de batería baja** - luz parpadeante y reducida
- ✅ **Advertencias visuales y sonoras** cuando la batería es baja/crítica
- ✅ **Baterías recogibles** para recargar
- ✅ Sistema **activable/desactivable** para diferentes modos de juego

### 💡 Sistema de Linterna Mejorado
- ✅ Encendido/apagado con **transiciones suaves**
- ✅ **Integrado con el sistema de batería**
- ✅ Efectos de **parpadeo** opcionales
- ✅ **Sombras suaves** para mejor atmósfera
- ✅ Sonidos de encendido/apagado

### 🎯 Sistema de Interacción
- ✅ **Raycast** para detectar objetos interactuables
- ✅ **Prompt de interacción** en UI
- ✅ Sistema extensible mediante interfaz `IInteractable`
- ✅ Soporte para **baterías y otros objetos**

### 🎨 UI/HUD Profesional
- ✅ **Indicador de batería** con barra y porcentaje
- ✅ **Colores dinámicos** según nivel de batería
- ✅ **Iconos** que cambian según el nivel
- ✅ **Animaciones** de pulso en batería crítica
- ✅ Mensajes de interacción

## 🎯 Requisitos
- Unity 2022.3 LTS o **Unity 6** (recomendado)
- Input System Package (incluido en el proyecto)
- TextMeshPro (incluido en el proyecto)
- Sistema operativo: Windows, macOS o Linux

## 🚀 Inicio Rápido

### 1. Abrir el Proyecto
1. Abre Unity Hub
2. Click en "Add" y selecciona la carpeta del proyecto
3. Abre con Unity 2022.3+ o Unity 6
4. Espera a que se importen los paquetes

### 2. Configurar Input System
Unity te preguntará si quieres usar el nuevo Input System. **Acepta y reinicia Unity**.

### 3. Abrir la Escena
```
Assets/Scenes/MainScene.unity
```

### 4. Presiona Play ▶️
¡El juego está listo para probar!

## 🎮 Controles

### Teclado + Mouse y Gamepad

| Acción | Teclado/Mouse | Gamepad |
|--------|---------------|---------|
| Mover | W/A/S/D | Stick Izquierdo |
| Mirar | Mouse | Stick Derecho |
| Saltar | Espacio | Botón A (Sur) |
| Correr | Shift Izquierdo | L3 (Click Stick Izq) |
| Linterna ON/OFF | F | Botón X (Oeste) |
| Interactuar | E | Botón B (Este) |
| Pausa | ESC | Start |

## 📁 Estructura del Proyecto

```
Spielberg73/
├── Assets/
│   ├── Scripts/
│   │   ├── FirstPersonController.cs          # Control del jugador (Input System)
│   │   ├── FlashlightController.cs          # Sistema de linterna
│   │   ├── BatterySystem.cs                 # Sistema de batería
│   │   ├── BatteryPickup.cs                 # Baterías recogibles
│   │   ├── InteractionSystem.cs             # Sistema de interacción
│   │   ├── IInteractable.cs                 # Interfaz para objetos
│   │   ├── BatteryUI.cs                     # UI de batería
│   │   └── GameManager.cs                   # Gestor del juego
│   ├── PlayerInputActions.inputactions      # Configuración de controles
│   ├── Scenes/
│   │   └── MainScene.unity                  # Escena principal
│   ├── Materials/
│   └── Prefabs/
├── ProjectSettings/
├── Packages/
│   └── manifest.json                        # Paquetes (Input System, etc.)
└── README.md
```

## 🔧 Scripts Principales

### FirstPersonController.cs
Controlador profesional con mecánicas estilo Half-Life:
- Input System con soporte para gamepad
- Aceleración y deceleración suaves
- Head Bob, FOV dinámico, inclinación de cámara
- Sistema de sprint y crouch
- Control aéreo realista

### BatterySystem.cs
Sistema completo de batería:
- Drenaje configurable
- Eventos para UI y efectos
- Modo activable/desactivable
- Recargas con baterías recogibles

### FlashlightController.cs
Linterna integrada con batería:
- Transiciones suaves de encendido/apagado
- Efectos de batería baja
- Parpadeo en batería crítica
- Sonidos opcionales

### InteractionSystem.cs
Sistema de interacción con objetos:
- Raycast para detectar objetos
- UI de interacción
- Extensible con IInteractable

### BatteryPickup.cs
Baterías recogibles:
- Efectos visuales (rotación, flotación)
- Configuración de cantidad de recarga
- Sonidos y partículas opcionales

### BatteryUI.cs
Interfaz de usuario para batería:
- Barra de progreso
- Porcentaje numérico
- Colores dinámicos
- Animaciones de advertencia

## 🎨 Efectos Visuales Profesionales

### Head Bob (Balanceo)
Simula el movimiento natural de la cabeza al caminar/correr
- Configurable en `FirstPersonController`
- Se puede desactivar si causa mareos

### FOV Dinámico
El campo de visión aumenta al correr para dar sensación de velocidad
- Base: 60°, Sprint: +10°
- Transiciones suaves

### Camera Tilt (Inclinación)
La cámara se inclina sutilmente al moverte lateralmente
- Simula inclinación corporal natural
- Recomendado: 2-3 grados

## 🔋 Sistema de Batería

### Configuración
```csharp
// En BatterySystem
batteryEnabled = true           // Activar sistema
maxBattery = 100f              // Batería máxima
drainRate = 5f                 // % por segundo
batteryPickupAmount = 25f      // Cantidad por batería
```

### Estados
```
100% ──────── Verde   (Full)
50%  ──────── Amarillo (Medium)
20%  ──────── Naranja  (Low) + Advertencia
5%   ──────── Rojo     (Critical) + Parpadeo
0%   ──────── Apagado automático
```

### Crear Baterías Recogibles
1. Crear objeto 3D (cubo, esfera, etc.)
2. Añadir componente `BatteryPickup`
3. Configurar cantidad (por defecto: 25%)
4. ¡Listo! El objeto flotará y rotará automáticamente

## 🎯 Sistema de Interacción

### Crear Objetos Interactuables
Implementa la interfaz `IInteractable`:

```csharp
public class MiObjeto : MonoBehaviour, IInteractable
{
    public string GetInteractionPrompt()
    {
        return "Presiona E para usar";
    }

    public void Interact(GameObject player)
    {
        Debug.Log("¡Interactuado!");
    }

    public bool CanInteract()
    {
        return true;
    }

    public Transform GetTransform()
    {
        return transform;
    }
}
```

## 🐛 Solución de Problemas

### El Input System no funciona
```
1. Window > Package Manager > Input System > Reinstall
2. Edit > Project Settings > Player > Active Input Handling > Input System Package (New)
3. Reiniciar Unity
```

### Los controles no responden
1. Verifica que `PlayerInputActions.inputactions` esté compilado
2. Revisa la consola en busca de errores
3. Intenta reimportar el asset

### El gamepad no funciona
1. Conecta el gamepad ANTES de abrir Unity
2. `Window > Analysis > Input Debugger` para ver dispositivos
3. Prueba con otro mando si es posible

### La batería no se drena
1. `BatterySystem.batteryEnabled = true`
2. Verifica que FlashlightController tenga referencia al BatterySystem
3. Revisa la consola

### HeadBob causa mareos
```csharp
// En FirstPersonController
enableHeadBob = false
```

## ⚙️ Configuraciones Recomendadas

### Modo Terror/Survival
```csharp
walkSpeed = 3.5f
sprintSpeed = 6f
drainRate = 10f              // Batería se drena rápido
batteryPickupAmount = 15f
lightIntensity = 2f          // Luz más débil
```

### Modo Exploración
```csharp
walkSpeed = 5f
sprintSpeed = 8f
drainRate = 3f               // Batería dura más
batteryPickupAmount = 30f
lightIntensity = 4f          // Luz más fuerte
```

### Sin Batería (Infinita)
```csharp
// En BatterySystem
batteryEnabled = false
```

## 🚀 Próximas Características Sugeridas

- 🎯 Sistema de inventario completo
- 👻 IA de enemigos que reaccionen a la luz
- 🗺️ Sistema de niveles/misiones
- 💾 Sistema de guardado y carga
- 🎵 Audio dinámico según situación
- 🌙 Ciclo día/noche
- 📱 Soporte para controles táctiles (móvil)

## 📝 Notas Técnicas

### Input System vs Old Input
Usamos el nuevo Input System porque:
- ✅ Soporte nativo para gamepad
- ✅ Remapping de controles en runtime
- ✅ Mejor arquitectura
- ✅ Múltiples dispositivos simultáneos

### Unity 6 Optimizado
Este proyecto aprovecha Unity 6 para:
- Mejor rendimiento del Input System
- Gráficos mejorados
- Herramientas de debugging avanzadas

## 📜 Licencia
Este proyecto es de código abierto y está disponible para uso educativo y personal.

## 👥 Créditos
- Desarrollado con Unity Engine 6
- Input System by Unity Technologies
- Inspirado en Half-Life, FEAR, Amnesia

---

**Versión:** 2.0
**Unity:** 6.0 / 2022.3 LTS
**Input System:** 1.7.0
