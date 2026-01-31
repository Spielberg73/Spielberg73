# 🌫️ Guía de Sistemas de Partículas Atmosféricas

## 📋 Tabla de Contenidos
1. [Introducción](#introducción)
2. [Sistema de Polvo en Luz](#sistema-de-polvo-en-luz)
3. [Sistema de Insectos](#sistema-de-insectos)
4. [Configuración Paso a Paso](#configuración-paso-a-paso)
5. [Optimización](#optimización)
6. [Consejos Profesionales](#consejos-profesionales)

---

## 🎯 Introducción

Este proyecto incluye dos sistemas de partículas atmosféricas profesionales que añaden realismo cinematográfico a tu juego:

- **Sistema de Polvo en Luz de Linterna**: Partículas de polvo flotante que solo aparecen en el cono de luz
- **Sistema de Insectos**: Enjambres de insectos con comportamiento realista en zonas específicas

### Características Principales

✅ **Polvo en Luz**:
- Emisión solo cuando la linterna está encendida
- Sincronización automática con el cono de luz
- Fade in/out suave
- Optimización con distance culling
- Densidad ajustable

✅ **Insectos**:
- 5 tipos de insectos (moscas, mosquitos, luciérnagas, polillas, jejenes)
- Movimiento errático realista
- Reacción a luz (atracción/repulsión)
- Audio posicional 3D
- Zonas activables por trigger

---

## 🌫️ Sistema de Polvo en Luz

### Arquitectura

El sistema consta de:
- **DustParticleController.cs**: Controlador principal del polvo
- **ParticleSystem**: Sistema de partículas de Unity
- Integración con **FlashlightController.cs**

### Configuración Rápida (5 minutos)

#### 1. Crear el Sistema de Polvo

**En la jerarquía:**
```
Player
└── PlayerCamera
    └── Flashlight (GameObject con FlashlightController)
        ├── FlashlightLight (Light component)
        └── DustParticles (NUEVO)
```

**Pasos:**
1. Click derecho en el GameObject `Flashlight` → Create Empty
2. Renombrar a `DustParticles`
3. Añadir `ParticleSystem` component
4. Añadir `DustParticleController` script
5. En `FlashlightController`, arrastrar `DustParticles` al campo `Dust Particles`

#### 2. Configurar el Particle System

**Main Module:**
```
Duration: 5.00
Looping: ✓
Start Lifetime: 5
Start Speed: 0.2
Start Size: 0.01 to 0.05
Start Rotation: Random
Start Color: Blanco (alpha ~30%)
Gravity Modifier: 0
Simulation Space: World
Max Particles: 1000
```

**Emission Module:**
```
Rate over Time: 100 (se controla por script)
```

**Shape Module:**
```
Shape: Cone
Angle: 45 (se sincroniza con linterna)
Radius: 5
Length: 10
Random Direction: 0.3
```

**Color over Lifetime:**
```
Gradient:
  0%   → Alpha 0 (invisible)
  20%  → Alpha 30% (fade in)
  80%  → Alpha 30% (mantiene)
  100% → Alpha 0 (fade out)
```

**Renderer:**
```
Render Mode: Billboard
Material: Default-Particle
Cast Shadows: Off
Receive Shadows: Off
```

#### 3. Configurar DustParticleController

**Parámetros Recomendados:**

```csharp
[Referencias]
Dust Particle System: (auto-assign)
Flashlight: (auto-assign o manual)

[Emisión]
Emission Rate When Active: 100
Dust Density Multiplier: 1.0 (normal)
Auto Activate With Flashlight: ✓

[Partículas]
Min Particle Size: 0.01
Max Particle Size: 0.05
Dust Speed: 0.2
Particle Lifetime: 5

[Forma del Emisor]
Cone Angle: 45 (auto-sync)
Cone Radius: 5
Cone Length: 10

[Efectos Visuales]
Dust Color: Blanco (R:1, G:1, B:1, A:0.3)
Affected By Light: ✓

[Optimización]
Max Render Distance: 50
Use Distance Culling: ✓
```

### Ajustes según Ambiente

**Ambiente Limpio (casa moderna):**
```
Emission Rate: 30-50
Density Multiplier: 0.5
Particle Size: 0.01-0.03
```

**Ambiente Normal (edificio abandonado):**
```
Emission Rate: 100
Density Multiplier: 1.0
Particle Size: 0.01-0.05
```

**Ambiente Muy Polvoriento (mina, sótano viejo):**
```
Emission Rate: 200-300
Density Multiplier: 2.0
Particle Size: 0.02-0.08
Color: Ligeramente amarillo/marrón
```

### API Pública

```csharp
// Activar/Desactivar manualmente
dustController.ActivateDust();
dustController.DeactivateDust();

// Ajustar densidad en runtime
dustController.SetDustDensity(2.0f); // Muy denso

// Ajustar forma del cono
dustController.SetConeAngle(60f);
dustController.SetConeLength(15f);

// Obtener info
int particleCount = dustController.GetActiveParticleCount();
```

---

## 🦟 Sistema de Insectos

### Arquitectura

El sistema consta de:
- **InsectSwarm.cs**: Comportamiento del enjambre
- **InsectZone.cs**: Zonas donde aparecen insectos
- **ParticleSystem**: Visualización de insectos
- **AudioSource**: Sonido ambiental

### Tipos de Insectos

| Tipo | Comportamiento | Luz | Sonido Sugerido |
|------|---------------|-----|-----------------|
| **Flies** (Moscas) | Errático (80%) | Repelidas | Zumbido medio |
| **Mosquitoes** | Muy errático (90%) | Repelidos | Zumbido agudo |
| **Fireflies** | Suave (30%), brillan | Neutral | Silencio/cricket |
| **Moths** | Moderado (50%) | **Atraídas** | Aleteo suave |
| **Gnats** | Extremo (100%) | Repelidos | Zumbido fino |

### Configuración Paso a Paso

#### 1. Crear Prefab de Enjambre

**Opción A: Manual**

1. Crear GameObject vacío → Renombrar `Swarm_Flies`
2. Añadir `ParticleSystem` component
3. Añadir `InsectSwarm` script
4. Añadir `AudioSource` component
5. Configurar según tipo de insecto

**Opción B: Procedural (automático)**

El sistema puede crear enjambres automáticamente si no proporcionas prefab.

#### 2. Configurar Particle System para Insectos

**Moscas Comunes:**
```
Main Module:
  Start Lifetime: Infinity
  Start Speed: 0 (controlado por script)
  Start Size: 0.02
  Start Color: Negro
  Simulation Space: World
  Max Particles: 50

Renderer:
  Material: Sprites-Default (partícula oscura)
  Render Mode: Billboard
```

**Luciérnagas:**
```
Main Module:
  Start Color: Amarillo brillante
  Start Size: 0.015

Renderer:
  Material: Material con emisión
  Render Mode: Billboard

(El script maneja la emisión automáticamente)
```

#### 3. Configurar InsectSwarm

```csharp
[Tipo]
Insect Type: Flies

[Referencias]
Insect Particle System: (auto-assign)
Ambient Audio Source: (auto-assign)
Insect Sound: (arrastrar clip de audio)

[Enjambre]
Insect Count: 50
Swarm Radius: 3.0
Move Speed: 2.0
Erratic Movement: 0.7 (70% aleatorio)

[Comportamiento]
Use Static Center: ✓
Swarm Center: (this transform)
Follow Target: ✗

[Reacción a Luz]
React To Light: ✓
Attracted To Light: ✗ (false = repelidas)
Light Reaction Strength: 2.0
Light Detection Radius: 10.0

[Apariencia]
Insect Size: 0.02
Insect Color: Negro

[Sonido]
Sound Volume: 0.3
Pitch Variation: 0.1
Max Sound Distance: 15

[Optimización]
Use Distance Culling: ✓
Max Render Distance: 50
```

#### 4. Crear Zona de Insectos

**En la jerarquía:**
```
Level
└── Environment
    └── InsectZones
        └── Zone_Bathroom (NUEVA)
```

**Pasos:**
1. Crear GameObject vacío → Renombrar `Zone_Bathroom`
2. Añadir `InsectZone` script (añade BoxCollider automáticamente)
3. Ajustar tamaño del BoxCollider (verde en Scene)
4. Configurar zona

#### 5. Configurar InsectZone

```csharp
[Zona]
Player Tag: "Player"
Activate On Player Enter: ✓
Persist After Activation: ✗
Always Active: ✗

[Enjambres] (Lista)
  [0] Swarm Config:
    Swarm Prefab: (opcional)
    Insect Type: Flies
    Insect Count: 50
    Swarm Radius: 3.0
    Relative Position: (0, 1, 0) // 1m arriba del centro
    Wander In Zone: ✓
    Wander Speed: 0.5

  [1] Swarm Config:
    Insect Type: Mosquitoes
    Insect Count: 30
    Swarm Radius: 2.0
    Relative Position: (2, 1.5, 1)
    Wander In Zone: ✗

[Ambiente]
Zone Description: "Baño abandonado"
Gizmo Color: Verde (0, 1, 0, 0.3)

[Audio Ambiental]
Zone Ambient Sound: (opcional, adicional)
Ambient Volume: 0.2
Use 3D Audio: ✓
```

### Ejemplos de Configuración por Escenario

#### Escenario 1: Sótano con Moscas

```csharp
Zone: Box de 5x3x5m
Swarms:
  - Flies x50, radio 2m, centro arriba
  - Flies x30, radio 1.5m, esquina
Audio: Zumbido bajo continuo
Activación: Al entrar
Persistencia: No
```

#### Escenario 2: Bosque con Luciérnagas (Noche)

```csharp
Zone: Box de 20x4x20m
Swarms:
  - Fireflies x100, radio 8m, vagan
  - Fireflies x80, radio 6m, vagan
Audio: Grillos (ambiental)
Activación: Siempre activo
Efecto: Emisión amarilla
```

#### Escenario 3: Cueva con Mosquitos

```csharp
Zone: Box irregular 8x4x12m
Swarms:
  - Gnats x150, radio 2m, estático
  - Mosquitoes x80, radio 3m, siguen jugador*
Audio: Zumbido agudo irritante
Activación: Al entrar
Persistencia: Sí

*Configurar Follow Target al jugador
```

#### Escenario 4: Luz Exterior con Polillas

```csharp
Zone: Esfera de 5m alrededor de lámpara
Swarms:
  - Moths x40, atraídas a luz
React To Light: ✓
Attracted To Light: ✓
Light Reaction Strength: 3.0
Audio: Aleteo suave
```

### API Pública

```csharp
// Cambiar tipo en runtime
swarm.SetInsectType(InsectSwarm.InsectType.Fireflies);

// Cambiar cantidad
swarm.SetInsectCount(100);

// Cambiar radio
swarm.SetSwarmRadius(5f);

// Zona - Activación manual
zone.ManualActivate();
zone.ManualDeactivate();

// Zona - Añadir enjambre dinámicamente
InsectZone.SwarmConfig newSwarm = new InsectZone.SwarmConfig();
newSwarm.insectType = InsectSwarm.InsectType.Mosquitoes;
newSwarm.insectCount = 50;
zone.AddSwarm(newSwarm);

// Zona - Eliminar enjambre
zone.RemoveSwarm(0); // índice
```

---

## ⚙️ Configuración Paso a Paso Completa

### Setup de Polvo (10 minutos)

**1. Preparar Linterna**
```
✓ FlashlightController existe
✓ Light component configurado
✓ Spot angle y range definidos
```

**2. Crear Sistema de Polvo**
```
1. Flashlight → Create Empty → "DustParticles"
2. Add Component → Particle System
3. Add Component → DustParticleController
4. Configurar ParticleSystem (ver arriba)
5. Configurar DustParticleController (ver arriba)
```

**3. Conectar a Linterna**
```
FlashlightController:
  └── Dust Particles: DustParticles
```

**4. Probar**
```
1. Play
2. Encender/apagar linterna (F)
3. Verificar polvo aparece/desaparece
4. Ajustar densidad según ambiente
```

### Setup de Insectos (15 minutos)

**1. Preparar Assets**
```
Necesitas:
  - Clips de audio de insectos
  - (Opcional) Textura de insecto para partículas
```

**2. Crear Prefab de Enjambre (opcional)**
```
1. Hierarchy → Create Empty → "Swarm_Flies"
2. Add Component → Particle System
3. Add Component → Audio Source
4. Add Component → InsectSwarm
5. Configurar todo
6. Arrastrar a carpeta Prefabs
7. Eliminar de scene
```

**3. Crear Zona**
```
1. En tu nivel, crear GameObject → "Zone_Area"
2. Add Component → InsectZone
3. Ajustar BoxCollider para cubrir área
4. Posicionar donde quieras insectos
```

**4. Configurar Enjambres en Zona**
```
InsectZone:
  ├── Swarms: Size 1
  │   └── [0]
  │       ├── Swarm Prefab: (opcional)
  │       ├── Insect Type: Flies
  │       ├── Insect Count: 50
  │       ├── Swarm Radius: 3
  │       └── Relative Position: (0, 1, 0)
```

**5. Probar**
```
1. Play
2. Entrar en la zona
3. Verificar insectos aparecen
4. Escuchar audio
5. Salir y verificar desactivación (si configurado)
```

---

## 🚀 Optimización

### Polvo en Luz

#### Rendimiento

**Móvil/Low-End:**
```
Emission Rate: 30-50
Max Particles: 300
Particle Size: Más grande (menos partículas)
Distance Culling: ✓ (30m)
```

**PC/High-End:**
```
Emission Rate: 200-300
Max Particles: 2000
Particle Size: Más pequeño (más detalle)
Distance Culling: ✓ (50m)
```

**VR:**
```
Emission Rate: 50-80
Max Particles: 500
Optimizar: Prioridad
Distance Culling: ✓ (20m)
```

#### Distance Culling

El sistema automáticamente:
- **70-100% distancia**: Reduce emisión gradualmente
- **>100% distancia**: Detiene completamente

```csharp
Use Distance Culling: ✓
Max Render Distance: 50
```

### Insectos

#### Rendimiento por Zona

**Recomendaciones:**

```
Zonas pequeñas (5x5m):
  - 1-2 enjambres
  - 30-50 insectos/enjambre
  - Audio 3D

Zonas medianas (10x10m):
  - 2-3 enjambres
  - 50-80 insectos/enjambre
  - Wandering activado

Zonas grandes (20x20m):
  - 3-5 enjambres distribuidos
  - 40-60 insectos/enjambre
  - Wandering + audio
```

#### Límites Sugeridos

| Plataforma | Enjambres Activos | Insectos Totales | Audio Sources |
|------------|-------------------|------------------|---------------|
| Móvil | 2-3 | 100-150 | 1-2 |
| PC Low | 4-6 | 200-300 | 2-3 |
| PC High | 8-12 | 500-800 | 4-6 |
| VR | 2-4 | 100-200 | 2-3 |

#### Distance Culling

```csharp
Use Distance Culling: ✓
Max Render Distance: 50

// Se activa/pausa automáticamente
```

#### Optimización de Zonas

**Activar solo cuando necesario:**
```csharp
Activate On Player Enter: ✓
Persist After Activation: ✗ // Desactivar al salir
```

**Zonas persistentes (decorativas):**
```csharp
Always Active: ✓
Insect Count: 20-30 (reducido)
Use Distance Culling: ✓
```

---

## 💡 Consejos Profesionales

### Polvo en Luz

#### 1. Realismo según Ambiente

**Variación de Color:**
```csharp
// Ambiente limpio
dustColor = new Color(1f, 1f, 1f, 0.2f); // Blanco tenue

// Ambiente industrial
dustColor = new Color(0.8f, 0.8f, 0.7f, 0.3f); // Gris

// Ambiente antiguo
dustColor = new Color(0.9f, 0.85f, 0.7f, 0.35f); // Amarillento
```

#### 2. Densidad Dinámica

Cambiar densidad según eventos:

```csharp
// Evento: Explosión/colapso
dustController.SetDustDensity(5.0f);
// Esperar 3 segundos
yield return new WaitForSeconds(3f);
// Volver a normal
dustController.SetDustDensity(1.0f);
```

#### 3. Sincronización con Batería

```csharp
// En FlashlightController
void UpdateBatteryEffects()
{
    float batteryPercent = batterySystem.GetBatteryPercentage();

    // Reducir polvo con batería baja (menos luz = menos visible)
    if (dustParticles != null)
    {
        float density = Mathf.Lerp(0.3f, 1f, batteryPercent / 100f);
        dustParticles.SetDustDensity(density);
    }
}
```

#### 4. Partículas y Post-Processing

Combinar con:
- **Volumetric Lighting**: Realza visibilidad del polvo
- **Bloom**: Hace brillar partículas cercanas a luz
- **Depth of Field**: Desenfoca polvo lejano (realismo)

### Insectos

#### 1. Comportamiento Contextual

**Insectos por Tipo de Ambiente:**

```
Baños/Agua: Mosquitoes, Gnats
Sótanos: Flies
Bosques noche: Fireflies
Luces exteriores: Moths
General sucio: Flies
```

#### 2. Reacción a Eventos

```csharp
// Cuando el jugador hace ruido
void OnPlayerMakesNoise()
{
    // Moscas huyen temporalmente
    swarm.SetSwarmRadius(6f); // Expandir
    swarm.SetInsectType(InsectSwarm.InsectType.Flies);

    // Volver a normal después de 2s
    StartCoroutine(ResetSwarmAfterDelay(2f));
}
```

#### 3. Audio Mixing

**Capas de Audio:**
```
- Audio ambiental de zona (base)
- Audio de cada enjambre (detalle)
- Atenuación por distancia

Configuración:
  Zone Audio Volume: 0.1-0.2 (sutil)
  Swarm Audio Volume: 0.2-0.4 (perceptible)
  3D Spatial Blend: 1.0
  Rolloff: Linear
```

#### 4. Variación Visual

**Para mayor realismo:**

```csharp
// Crear varios enjambres con ligeras variaciones
Swarm 1: Count 50, Radius 3, Speed 2.0, Erratic 0.7
Swarm 2: Count 40, Radius 2.5, Speed 1.8, Erratic 0.8
Swarm 3: Count 60, Radius 3.5, Speed 2.2, Erratic 0.6

// Resultado: Movimiento más orgánico y natural
```

#### 5. Luciérnagas Especiales

**Efecto de parpadeo:**

Configurar en InsectSwarm:
```csharp
Insect Type: Fireflies
Emit Light: ✓
Emission Color: Amarillo (1, 0.9, 0.3)
Emission Intensity: 1.0-1.5

// Añadir script adicional para parpadeo
```

Script ejemplo de parpadeo:
```csharp
// FireflyFlicker.cs
void Update()
{
    float pulse = Mathf.PingPong(Time.time * 2f, 1f);
    emissionIntensity = Mathf.Lerp(0.3f, 1.5f, pulse);
}
```

#### 6. Insectos que Siguen al Jugador

```csharp
// Mosquitos molestos
InsectSwarm:
  Follow Target: Player Transform
  Follow Speed: 0.8 (más lento que jugador)
  Swarm Radius: 2.0 (cerca)

// Se mantienen cerca pero no exactamente encima
```

---

## 🎬 Casos de Uso Cinemáticos

### Escena 1: Entrada a Edificio Abandonado

```
1. Jugador entra al edificio
2. Enciende linterna
3. EFECTO: Polvo visible en luz (densidad 2.0)
4. Zona de moscas se activa en esquina
5. Audio: Zumbido lejano
6. Jugador se acerca → audio aumenta
7. Moscas reaccionan a luz (se alejan)
```

### Escena 2: Sótano con Batería Baja

```
1. Batería al 15%
2. Luz parpadea
3. EFECTO: Polvo parpadea con luz
4. Jugador ve siluetas de moscas en oscuridad
5. Batería al 5%
6. Luz muy débil, polvo apenas visible
7. Mosquitos se acercan (menos luz = más atrevidos)
```

### Escena 3: Bosque Nocturno Mágico

```
1. Zona exterior grande
2. 3 enjambres de luciérnagas activos
3. Wandering en zona de 30x30m
4. EFECTO: Puntos de luz flotantes
5. Audio: Grillos suaves
6. Jugador apaga linterna para verlas mejor
7. Sin polvo (aire libre limpio)
```

---

## 📝 Checklist de Implementación

### Sistema de Polvo ✓

```
□ ParticleSystem creado y configurado
□ DustParticleController añadido
□ Conectado a FlashlightController
□ Cone angle sincronizado con linterna
□ Densidad ajustada según ambiente
□ Distance culling activado
□ Probado encender/apagar
□ Rendimiento aceptable (FPS)
```

### Sistema de Insectos ✓

```
□ Prefab de enjambre creado (opcional)
□ InsectSwarm configurado
□ Audio de insectos asignado
□ Zona creada (InsectZone)
□ BoxCollider ajustado a área
□ Enjambres añadidos a lista
□ Tipo de insecto apropiado
□ Probado activación por trigger
□ Probado reacción a luz (si aplica)
□ Audio 3D funcional
□ Distance culling activado
□ Rendimiento aceptable
```

---

## 🐛 Troubleshooting

### Polvo no Aparece

**Problema**: No veo partículas de polvo.

**Soluciones**:
```
1. Verificar flashlight.enabled == true
2. Verificar dustParticles conectado en inspector
3. Verificar Emission Rate > 0
4. Verificar Max Particles > 0
5. Verificar cámara dentro de Max Render Distance
6. Verificar Alpha del color > 0
7. En Scene view, verificar partículas existen (modo wireframe)
```

### Polvo No Se Sincroniza con Linterna

**Problema**: Polvo sigue visible cuando linterna apagada.

**Soluciones**:
```
1. Verificar Auto Activate With Flashlight: ✓
2. Verificar referencia a Light asignada
3. Verificar FlashlightController llama ActivateDust/DeactivateDust
4. Debug.Log en TurnOn/TurnOff para confirmar llamadas
```

### Insectos No Aparecen

**Problema**: Entro a zona pero no veo insectos.

**Soluciones**:
```
1. Verificar Player Tag == "Player"
2. Verificar BoxCollider.isTrigger == true
3. Verificar lista Swarms.Count > 0
4. Verificar Insect Count > 0
5. Verificar zona activada (Debug.Log en OnTriggerEnter)
6. Verificar cámara dentro de Max Render Distance
7. Verificar ParticleSystem en prefab/generado
```

### Insectos No Se Mueven

**Problema**: Insectos aparecen pero están estáticos.

**Soluciones**:
```
1. Verificar Move Speed > 0
2. Verificar Swarm Radius > 0
3. Verificar script InsectSwarm habilitado
4. Verificar ParticleSystem.main.simulationSpace == World
5. Verificar Start Speed == 0 (movimiento por script)
```

### Rendimiento Bajo

**Problema**: FPS baja con sistemas activos.

**Soluciones Polvo**:
```
1. Reducir Emission Rate (100 → 50)
2. Reducir Max Particles (1000 → 500)
3. Reducir Max Render Distance (50 → 30)
4. Aumentar tamaño partículas (menos partículas)
5. Desactivar Affected By Light si no es crítico
```

**Soluciones Insectos**:
```
1. Reducir Insect Count (50 → 30)
2. Reducir número de enjambres
3. Desactivar Wander In Zone
4. Aumentar distance culling (activar más agresivo)
5. Desactivar React To Light si no es necesario
6. Reducir Update frequency (modificar script)
```

### Audio No Se Escucha

**Problema**: Insectos visuales OK pero sin sonido.

**Soluciones**:
```
1. Verificar AudioClip asignado
2. Verificar AudioSource.volume > 0
3. Verificar AudioSource no está muted
4. Verificar distancia < Max Sound Distance
5. Verificar Audio Listener en cámara
6. Verificar Audio Mixer no silenciado
7. Aumentar Sound Volume (0.3 → 0.5)
```

---

## 📚 Recursos Adicionales

### Assets Recomendados

**Audio de Insectos:**
- Freesound.org: "fly buzzing", "mosquito", "cricket"
- Búsqueda: "insect swarm", "bug sounds"

**Texturas de Partículas:**
- Polvo: Texturas de círculos suaves con alpha
- Insectos: Sprites pequeños oscuros

### Valores de Referencia AAA

**The Last of Us (Naughty Dog):**
- Polvo denso en ambientes cerrados
- Densidad: ~2.0-3.0
- Tamaño variable: 0.01-0.1

**Resident Evil (Capcom):**
- Moscas en áreas infectadas
- Enjambres: 40-80 insectos
- Audio prominente: 0.4-0.6 volumen

**Alien Isolation (Creative Assembly):**
- Atmósfera de partículas constante
- Polvo + vapor + humo combinados
- Densidad baja continua: 0.5-1.0

---

## ✨ Próximos Pasos

Una vez dominados estos sistemas, puedes expandir con:

1. **Vapor/Humo**: Similar a polvo pero con movimiento ascendente
2. **Lluvia Interior**: Goteras en techos
3. **Gotas de Agua**: En linternas después de lluvia
4. **Arañas**: Similar a insectos pero en techos/paredes
5. **Ratas**: Partículas de sombras que corren
6. **Pájaros**: Enjambres voladores exteriores

---

## 🎓 Resumen Ejecutivo

**Sistema de Polvo:**
- ✅ Realismo cinematográfico AAA
- ✅ Auto-sincronización con linterna
- ✅ Optimizado con culling
- ✅ Configurable por ambiente
- ⏱️ Setup: 5-10 minutos

**Sistema de Insectos:**
- ✅ 5 tipos de insectos diferentes
- ✅ Comportamiento realista con IA
- ✅ Zonas activables por trigger
- ✅ Audio posicional 3D
- ⏱️ Setup: 15-20 minutos

**Ambos sistemas juntos transformarán tu juego en una experiencia atmosférica profesional.**

---

**Creado para Unity 6**
**Compatible con Unity 2022.3 LTS**
**Versión: 1.0**
**Última actualización: 2026**
