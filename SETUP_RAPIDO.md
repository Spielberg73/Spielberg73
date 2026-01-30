# Guía de Configuración Rápida

## Pasos Mínimos para Empezar

### 1. Abrir en Unity
1. Abre Unity Hub
2. Click en "Add" → Selecciona esta carpeta
3. Abre el proyecto

### 2. Crear Escena Básica (5 minutos)

#### A. Crear el Jugador
```
1. GameObject > Create Empty → Nombrar "Player"
2. Add Component > Character Controller
3. Add Component > FirstPersonController
4. Crear hijo vacío → Nombrar "Camera" (posición Y: 0.6)
5. Add Component > Camera (en el objeto Camera)
6. Crear hijo de Camera → Nombrar "Flashlight"
7. Add Component > FlashlightController (en Flashlight)
8. Asignar Camera en FirstPersonController (arrastra el objeto Camera)
```

#### B. Crear el Mundo
```
1. GameObject > 3D Object > Plane (suelo)
   - Escalar: (10, 1, 10)
2. GameObject > 3D Object > Cube (varios cubos como obstáculos)
```

#### C. Configurar Oscuridad
```
1. Window > Rendering > Lighting
2. Environment tab:
   - Skybox Material: None
   - Environment Lighting > Source: Color
   - Ambient Color: Negro (0,0,0)
3. Eliminar "Directional Light" de la jerarquía
```

### 3. Probar el Juego
1. Click en Play ▶️
2. Usa WASD para moverte
3. Presiona F para encender/apagar linterna

## Estructura Jerárquica Final

```
Hierarchy
├── Player
│   ├── [CharacterController]
│   ├── [FirstPersonController]
│   └── Camera
│       ├── [Camera]
│       └── Flashlight
│           └── [FlashlightController]
├── Plane (suelo)
└── Cubes (obstáculos)
```

## Controles
- **WASD**: Mover
- **Mouse**: Mirar
- **F**: Linterna ON/OFF
- **Space**: Saltar
- **Shift**: Correr
- **ESC**: Liberar cursor

## Ajustes Recomendados

### En FirstPersonController:
- Walk Speed: 5
- Run Speed: 8
- Mouse Sensitivity: 2

### En FlashlightController:
- Light Intensity: 3
- Light Range: 15
- Spot Angle: 60

## Problemas Comunes

### No veo nada
→ Oscurece la escena (ver paso 2C)

### Linterna muy débil
→ Aumenta Light Intensity a 5-8

### Movimiento muy lento/rápido
→ Ajusta Walk Speed en FirstPersonController

### Mouse no funciona
→ Click en ventana de juego + ESC para bloquear cursor
