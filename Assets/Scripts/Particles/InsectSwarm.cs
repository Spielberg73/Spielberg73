using UnityEngine;

/// <summary>
/// Controla el comportamiento de un enjambre de insectos voladores.
/// Simula movimiento realista de moscas, mosquitos y otros insectos con vuelo errático.
///
/// Características:
/// - Movimiento errático y realista
/// - Comportamiento de enjambre (se mantienen juntos)
/// - Reacción a luz (atraídos o repelidos)
/// - Sonido ambiental posicional
/// - Optimización con LOD
/// - Diferentes tipos de insectos (moscas, mosquitos, luciérnagas)
/// </summary>
public class InsectSwarm : MonoBehaviour
{
    /// <summary>
    /// Tipos de insectos disponibles
    /// </summary>
    public enum InsectType
    {
        Flies,          // Moscas comunes
        Mosquitoes,     // Mosquitos
        Fireflies,      // Luciérnagas (brillan)
        Moths,          // Polillas (atraídas por luz)
        Gnats           // Jejenes/mosquitos pequeños
    }

    [Header("Tipo de Insecto")]
    [Tooltip("Tipo de insecto que forma el enjambre")]
    [SerializeField] private InsectType insectType = InsectType.Flies;

    [Header("Referencias")]
    [Tooltip("Sistema de partículas para los insectos")]
    [SerializeField] private ParticleSystem insectParticleSystem;

    [Tooltip("Audio source para sonido ambiental del enjambre")]
    [SerializeField] private AudioSource ambientAudioSource;

    [Tooltip("Clip de audio del zumbido/sonido de insectos")]
    [SerializeField] private AudioClip insectSound;

    [Header("Configuración del Enjambre")]
    [Tooltip("Número de insectos en el enjambre")]
    [SerializeField] private int insectCount = 50;

    [Tooltip("Radio del área donde se mueven los insectos")]
    [SerializeField] private float swarmRadius = 3f;

    [Tooltip("Velocidad de movimiento de los insectos")]
    [SerializeField] private float moveSpeed = 2f;

    [Tooltip("Intensidad del movimiento errático (0 = suave, 1 = muy errático)")]
    [SerializeField] [Range(0f, 1f)] private float erraticMovement = 0.7f;

    [Header("Comportamiento")]
    [Tooltip("El enjambre se mueve alrededor de un punto central")]
    [SerializeField] private bool useStaticCenter = true;

    [Tooltip("Punto central del enjambre (si es estático)")]
    [SerializeField] private Transform swarmCenter;

    [Tooltip("El enjambre sigue a un objetivo")]
    [SerializeField] private bool followTarget = false;

    [Tooltip("Objetivo a seguir (opcional)")]
    [SerializeField] private Transform targetToFollow;

    [Tooltip("Velocidad a la que el enjambre sigue al objetivo")]
    [SerializeField] private float followSpeed = 1f;

    [Header("Reacción a la Luz")]
    [Tooltip("Los insectos reaccionan a la luz")]
    [SerializeField] private bool reactToLight = true;

    [Tooltip("Tipo de reacción (true = atraídos, false = repelidos)")]
    [SerializeField] private bool attractedToLight = true;

    [Tooltip("Intensidad de la reacción a la luz")]
    [SerializeField] private float lightReactionStrength = 2f;

    [Tooltip("Radio de detección de luz")]
    [SerializeField] private float lightDetectionRadius = 10f;

    [Header("Apariencia")]
    [Tooltip("Tamaño de los insectos")]
    [SerializeField] private float insectSize = 0.02f;

    [Tooltip("Color de los insectos")]
    [SerializeField] private Color insectColor = Color.black;

    [Tooltip("Emisión de luz (para luciérnagas)")]
    [SerializeField] private bool emitLight = false;

    [Tooltip("Color de emisión (luciérnagas)")]
    [SerializeField] private Color emissionColor = Color.yellow;

    [Tooltip("Intensidad de emisión")]
    [SerializeField] [Range(0f, 2f)] private float emissionIntensity = 1f;

    [Header("Sonido")]
    [Tooltip("Volumen del sonido ambiental")]
    [SerializeField] [Range(0f, 1f)] private float soundVolume = 0.3f;

    [Tooltip("Variación de pitch del sonido")]
    [SerializeField] [Range(0f, 0.5f)] private float pitchVariation = 0.1f;

    [Tooltip("Distancia máxima para escuchar el sonido")]
    [SerializeField] private float maxSoundDistance = 15f;

    [Header("Optimización")]
    [Tooltip("Desactivar el enjambre si está muy lejos de la cámara")]
    [SerializeField] private bool useDistanceCulling = true;

    [Tooltip("Distancia máxima de renderizado")]
    [SerializeField] private float maxRenderDistance = 50f;

    // Estado interno
    private ParticleSystem.Particle[] particles;
    private Vector3[] velocities;
    private Vector3[] targetPositions;
    private Vector3 currentSwarmCenter;
    private Transform mainCameraTransform;
    private Light nearestLight;
    private float soundTimer = 0f;
    private bool isActive = true;

    void Start()
    {
        InitializeSwarm();
        mainCameraTransform = Camera.main?.transform;
    }

    void Update()
    {
        if (!isActive) return;

        UpdateDistanceCulling();
        UpdateSwarmCenter();
        UpdateParticleMovement();
        UpdateSound();
        FindNearestLight();
    }

    /// <summary>
    /// Inicializa el sistema de partículas y arrays de control
    /// </summary>
    private void InitializeSwarm()
    {
        if (insectParticleSystem == null)
        {
            Debug.LogError($"InsectSwarm en {gameObject.name}: No se asignó el ParticleSystem!");
            return;
        }

        // Configurar el sistema de partículas
        var main = insectParticleSystem.main;
        main.maxParticles = insectCount;
        main.startSize = insectSize;
        main.startColor = insectColor;
        main.startSpeed = 0f;
        main.startLifetime = Mathf.Infinity;
        main.loop = false;
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;

        // Configurar emisión si es luciérnaga
        if (emitLight && insectType == InsectType.Fireflies)
        {
            var colorOverLifetime = insectParticleSystem.colorOverLifetime;
            colorOverLifetime.enabled = true;

            Gradient gradient = new Gradient();
            Color emissive = emissionColor * emissionIntensity;
            gradient.SetKeys(
                new GradientColorKey[] {
                    new GradientColorKey(emissive, 0.0f),
                    new GradientColorKey(emissive, 1.0f)
                },
                new GradientAlphaKey[] {
                    new GradientAlphaKey(1.0f, 0.0f),
                    new GradientAlphaKey(1.0f, 1.0f)
                }
            );
            colorOverLifetime.color = gradient;
        }

        // Inicializar arrays
        particles = new ParticleSystem.Particle[insectCount];
        velocities = new Vector3[insectCount];
        targetPositions = new Vector3[insectCount];

        // Establecer centro inicial
        currentSwarmCenter = swarmCenter != null ? swarmCenter.position : transform.position;

        // Emitir partículas iniciales
        insectParticleSystem.Emit(insectCount);
        insectParticleSystem.GetParticles(particles);

        // Posicionar partículas aleatoriamente dentro del radio
        for (int i = 0; i < particles.Length; i++)
        {
            particles[i].position = currentSwarmCenter + Random.insideUnitSphere * swarmRadius;
            particles[i].startLifetime = Mathf.Infinity;
            particles[i].remainingLifetime = Mathf.Infinity;
            velocities[i] = Random.insideUnitSphere * moveSpeed;
            targetPositions[i] = GetRandomTargetPosition();
        }

        insectParticleSystem.SetParticles(particles, particles.Length);

        // Configurar audio
        SetupAudio();

        // Ajustar comportamiento según tipo de insecto
        ConfigureInsectBehavior();
    }

    /// <summary>
    /// Configura el audio ambiental del enjambre
    /// </summary>
    private void SetupAudio()
    {
        if (ambientAudioSource == null)
        {
            ambientAudioSource = gameObject.AddComponent<AudioSource>();
        }

        ambientAudioSource.clip = insectSound;
        ambientAudioSource.loop = true;
        ambientAudioSource.spatialBlend = 1f; // 3D
        ambientAudioSource.volume = soundVolume;
        ambientAudioSource.maxDistance = maxSoundDistance;
        ambientAudioSource.rolloffMode = AudioRolloffMode.Linear;
        ambientAudioSource.pitch = 1f + Random.Range(-pitchVariation, pitchVariation);

        if (insectSound != null)
        {
            ambientAudioSource.Play();
        }
    }

    /// <summary>
    /// Ajusta parámetros según el tipo de insecto
    /// </summary>
    private void ConfigureInsectBehavior()
    {
        switch (insectType)
        {
            case InsectType.Flies:
                erraticMovement = 0.8f;
                moveSpeed = 2f;
                attractedToLight = false;
                break;

            case InsectType.Mosquitoes:
                erraticMovement = 0.9f;
                moveSpeed = 1.5f;
                attractedToLight = false;
                break;

            case InsectType.Fireflies:
                erraticMovement = 0.3f;
                moveSpeed = 0.8f;
                attractedToLight = false;
                emitLight = true;
                break;

            case InsectType.Moths:
                erraticMovement = 0.5f;
                moveSpeed = 2.5f;
                attractedToLight = true;
                reactToLight = true;
                break;

            case InsectType.Gnats:
                erraticMovement = 1f;
                moveSpeed = 1f;
                attractedToLight = false;
                break;
        }
    }

    /// <summary>
    /// Actualiza el centro del enjambre según configuración
    /// </summary>
    private void UpdateSwarmCenter()
    {
        if (followTarget && targetToFollow != null)
        {
            currentSwarmCenter = Vector3.Lerp(
                currentSwarmCenter,
                targetToFollow.position,
                Time.deltaTime * followSpeed
            );
        }
        else if (useStaticCenter && swarmCenter != null)
        {
            currentSwarmCenter = swarmCenter.position;
        }

        // Posicionar el audio en el centro del enjambre
        if (ambientAudioSource != null)
        {
            ambientAudioSource.transform.position = currentSwarmCenter;
        }
    }

    /// <summary>
    /// Actualiza el movimiento de cada partícula del enjambre
    /// </summary>
    private void UpdateParticleMovement()
    {
        if (insectParticleSystem == null) return;

        int particleCount = insectParticleSystem.GetParticles(particles);

        for (int i = 0; i < particleCount; i++)
        {
            // Calcular dirección hacia el objetivo individual
            Vector3 toTarget = targetPositions[i] - particles[i].position;

            // Si llegó cerca del objetivo, elegir uno nuevo
            if (toTarget.magnitude < 0.5f)
            {
                targetPositions[i] = GetRandomTargetPosition();
                toTarget = targetPositions[i] - particles[i].position;
            }

            // Fuerza hacia el objetivo
            Vector3 targetForce = toTarget.normalized * moveSpeed;

            // Fuerza hacia el centro del enjambre (cohesión)
            Vector3 centerForce = (currentSwarmCenter - particles[i].position).normalized * moveSpeed * 0.5f;

            // Movimiento errático aleatorio
            Vector3 randomForce = new Vector3(
                Mathf.PerlinNoise(Time.time * 2f + i, 0f) - 0.5f,
                Mathf.PerlinNoise(0f, Time.time * 2f + i) - 0.5f,
                Mathf.PerlinNoise(Time.time * 2f + i, Time.time * 2f + i) - 0.5f
            ) * moveSpeed * erraticMovement;

            // Reacción a la luz
            Vector3 lightForce = Vector3.zero;
            if (reactToLight && nearestLight != null)
            {
                Vector3 toLight = nearestLight.transform.position - particles[i].position;
                float distance = toLight.magnitude;

                if (distance < lightDetectionRadius)
                {
                    float strength = lightReactionStrength * (1f - distance / lightDetectionRadius);
                    lightForce = toLight.normalized * strength * (attractedToLight ? 1f : -1f);
                }
            }

            // Combinar fuerzas
            Vector3 totalForce = targetForce + centerForce + randomForce + lightForce;
            velocities[i] = Vector3.Lerp(velocities[i], totalForce, Time.deltaTime * 2f);

            // Aplicar velocidad
            particles[i].position += velocities[i] * Time.deltaTime;

            // Mantener dentro del radio del enjambre
            Vector3 fromCenter = particles[i].position - currentSwarmCenter;
            if (fromCenter.magnitude > swarmRadius)
            {
                particles[i].position = currentSwarmCenter + fromCenter.normalized * swarmRadius;
            }
        }

        insectParticleSystem.SetParticles(particles, particleCount);
    }

    /// <summary>
    /// Genera una posición objetivo aleatoria dentro del radio del enjambre
    /// </summary>
    private Vector3 GetRandomTargetPosition()
    {
        return currentSwarmCenter + Random.insideUnitSphere * swarmRadius * 0.8f;
    }

    /// <summary>
    /// Busca la luz más cercana al enjambre
    /// </summary>
    private void FindNearestLight()
    {
        if (!reactToLight) return;

        Light[] lights = FindObjectsOfType<Light>();
        float closestDistance = lightDetectionRadius;
        nearestLight = null;

        foreach (Light light in lights)
        {
            if (!light.enabled) continue;

            float distance = Vector3.Distance(currentSwarmCenter, light.transform.position);
            if (distance < closestDistance)
            {
                closestDistance = distance;
                nearestLight = light;
            }
        }
    }

    /// <summary>
    /// Actualiza el sonido del enjambre
    /// </summary>
    private void UpdateSound()
    {
        if (ambientAudioSource == null || insectSound == null) return;

        // Variar ligeramente el pitch con el tiempo para mayor realismo
        soundTimer += Time.deltaTime;
        if (soundTimer > 2f)
        {
            soundTimer = 0f;
            ambientAudioSource.pitch = 1f + Random.Range(-pitchVariation, pitchVariation);
        }
    }

    /// <summary>
    /// Desactiva el enjambre si está muy lejos de la cámara para optimización
    /// </summary>
    private void UpdateDistanceCulling()
    {
        if (!useDistanceCulling || mainCameraTransform == null) return;

        float distance = Vector3.Distance(currentSwarmCenter, mainCameraTransform.position);

        if (distance > maxRenderDistance)
        {
            if (isActive)
            {
                isActive = false;
                if (insectParticleSystem != null)
                    insectParticleSystem.Pause();
                if (ambientAudioSource != null)
                    ambientAudioSource.Pause();
            }
        }
        else
        {
            if (!isActive)
            {
                isActive = true;
                if (insectParticleSystem != null)
                    insectParticleSystem.Play();
                if (ambientAudioSource != null)
                    ambientAudioSource.UnPause();
            }
        }
    }

    /// <summary>
    /// Cambia el tipo de insecto en tiempo de ejecución
    /// </summary>
    public void SetInsectType(InsectType type)
    {
        insectType = type;
        ConfigureInsectBehavior();
    }

    /// <summary>
    /// Cambia el número de insectos en el enjambre
    /// </summary>
    public void SetInsectCount(int count)
    {
        insectCount = Mathf.Max(1, count);
        InitializeSwarm();
    }

    /// <summary>
    /// Establece el radio del enjambre
    /// </summary>
    public void SetSwarmRadius(float radius)
    {
        swarmRadius = Mathf.Max(0.5f, radius);
    }

    #if UNITY_EDITOR
    /// <summary>
    /// Dibuja el área del enjambre en el editor
    /// </summary>
    private void OnDrawGizmosSelected()
    {
        Vector3 center = swarmCenter != null ? swarmCenter.position : transform.position;

        // Dibujar esfera del radio del enjambre
        Gizmos.color = new Color(0f, 1f, 0f, 0.2f);
        Gizmos.DrawWireSphere(center, swarmRadius);

        // Dibujar radio de detección de luz
        if (reactToLight)
        {
            Gizmos.color = new Color(1f, 1f, 0f, 0.1f);
            Gizmos.DrawWireSphere(center, lightDetectionRadius);
        }
    }
    #endif
}
