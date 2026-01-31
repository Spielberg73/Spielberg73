using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Define una zona específica donde aparecen insectos.
/// Permite crear áreas con diferentes tipos de insectos y configurar su aparición.
///
/// Características:
/// - Activación por proximidad del jugador
/// - Configuración por zona (tipo de insecto, cantidad, etc.)
/// - Múltiples enjambres por zona
/// - Sistema de spawn dinámico
/// - Triggers visuales en el editor
/// </summary>
[RequireComponent(typeof(BoxCollider))]
public class InsectZone : MonoBehaviour
{
    /// <summary>
    /// Configuración de un enjambre dentro de la zona
    /// </summary>
    [System.Serializable]
    public class SwarmConfig
    {
        [Tooltip("Prefab del enjambre a instanciar")]
        public GameObject swarmPrefab;

        [Tooltip("Tipo de insecto")]
        public InsectSwarm.InsectType insectType = InsectSwarm.InsectType.Flies;

        [Tooltip("Número de insectos")]
        public int insectCount = 50;

        [Tooltip("Radio del enjambre")]
        public float swarmRadius = 3f;

        [Tooltip("Posición relativa dentro de la zona")]
        public Vector3 relativePosition = Vector3.zero;

        [Tooltip("El enjambre se mueve aleatoriamente dentro de la zona")]
        public bool wanderInZone = false;

        [Tooltip("Velocidad de movimiento del enjambre en la zona")]
        public float wanderSpeed = 0.5f;

        [HideInInspector]
        public GameObject spawnedSwarm;
    }

    [Header("Configuración de la Zona")]
    [Tooltip("Tag del jugador para activar la zona")]
    [SerializeField] private string playerTag = "Player";

    [Tooltip("Activar solo cuando el jugador entra en la zona")]
    [SerializeField] private bool activateOnPlayerEnter = true;

    [Tooltip("Mantener activo incluso cuando el jugador sale")]
    [SerializeField] private bool persistAfterActivation = false;

    [Tooltip("Zona siempre activa (ignorar triggers)")]
    [SerializeField] private bool alwaysActive = false;

    [Header("Enjambres")]
    [Tooltip("Lista de enjambres que aparecen en esta zona")]
    [SerializeField] private List<SwarmConfig> swarms = new List<SwarmConfig>();

    [Header("Ambiente de la Zona")]
    [Tooltip("Descripción de la zona (solo para organización)")]
    [SerializeField] private string zoneDescription = "Zona de insectos";

    [Tooltip("Color de visualización en el editor")]
    [SerializeField] private Color gizmoColor = new Color(0f, 1f, 0f, 0.3f);

    [Header("Audio Ambiental de Zona")]
    [Tooltip("Sonido ambiental de la zona (opcional, adicional al de los insectos)")]
    [SerializeField] private AudioClip zoneAmbientSound;

    [Tooltip("Volumen del audio ambiental")]
    [SerializeField] [Range(0f, 1f)] private float ambientVolume = 0.2f;

    [Tooltip("Audio es 3D o 2D")]
    [SerializeField] private bool use3DAudio = true;

    // Estado interno
    private BoxCollider zoneCollider;
    private AudioSource zoneAudioSource;
    private bool isActive = false;
    private bool hasBeenActivated = false;
    private List<Vector3> wanderTargets = new List<Vector3>();

    void Start()
    {
        InitializeZone();

        if (alwaysActive)
        {
            ActivateZone();
        }
    }

    void Update()
    {
        if (isActive)
        {
            UpdateWanderingSwarms();
        }
    }

    /// <summary>
    /// Inicializa la zona y sus componentes
    /// </summary>
    private void InitializeZone()
    {
        // Configurar collider como trigger
        zoneCollider = GetComponent<BoxCollider>();
        zoneCollider.isTrigger = true;

        // Configurar audio ambiental si existe
        if (zoneAmbientSound != null)
        {
            SetupZoneAudio();
        }

        // Inicializar targets de wandering
        foreach (var swarm in swarms)
        {
            wanderTargets.Add(GetRandomPositionInZone());
        }
    }

    /// <summary>
    /// Configura el audio ambiental de la zona
    /// </summary>
    private void SetupZoneAudio()
    {
        zoneAudioSource = gameObject.AddComponent<AudioSource>();
        zoneAudioSource.clip = zoneAmbientSound;
        zoneAudioSource.loop = true;
        zoneAudioSource.volume = ambientVolume;
        zoneAudioSource.playOnAwake = false;

        if (use3DAudio)
        {
            zoneAudioSource.spatialBlend = 1f;
            zoneAudioSource.maxDistance = zoneCollider.size.magnitude;
            zoneAudioSource.rolloffMode = AudioRolloffMode.Linear;
        }
        else
        {
            zoneAudioSource.spatialBlend = 0f;
        }
    }

    /// <summary>
    /// Activa la zona e instancia los enjambres
    /// </summary>
    private void ActivateZone()
    {
        if (isActive && !alwaysActive) return;

        isActive = true;
        hasBeenActivated = true;

        // Reproducir audio ambiental
        if (zoneAudioSource != null && !zoneAudioSource.isPlaying)
        {
            zoneAudioSource.Play();
        }

        // Instanciar enjambres
        for (int i = 0; i < swarms.Count; i++)
        {
            SpawnSwarm(i);
        }

        Debug.Log($"Zona de insectos '{zoneDescription}' activada con {swarms.Count} enjambres");
    }

    /// <summary>
    /// Desactiva la zona y destruye los enjambres
    /// </summary>
    private void DeactivateZone()
    {
        if (!isActive || persistAfterActivation || alwaysActive) return;

        isActive = false;

        // Detener audio ambiental
        if (zoneAudioSource != null && zoneAudioSource.isPlaying)
        {
            zoneAudioSource.Stop();
        }

        // Destruir enjambres
        foreach (var swarm in swarms)
        {
            if (swarm.spawnedSwarm != null)
            {
                Destroy(swarm.spawnedSwarm);
                swarm.spawnedSwarm = null;
            }
        }

        Debug.Log($"Zona de insectos '{zoneDescription}' desactivada");
    }

    /// <summary>
    /// Instancia un enjambre específico
    /// </summary>
    private void SpawnSwarm(int index)
    {
        if (index < 0 || index >= swarms.Count) return;

        SwarmConfig config = swarms[index];

        // Si ya existe, no crear otro
        if (config.spawnedSwarm != null) return;

        // Calcular posición de spawn
        Vector3 spawnPosition = transform.position + config.relativePosition;

        // Instanciar prefab o crear GameObject con InsectSwarm
        if (config.swarmPrefab != null)
        {
            config.spawnedSwarm = Instantiate(config.swarmPrefab, spawnPosition, Quaternion.identity, transform);
        }
        else
        {
            // Crear enjambre proceduralmente
            config.spawnedSwarm = new GameObject($"Swarm_{config.insectType}_{index}");
            config.spawnedSwarm.transform.position = spawnPosition;
            config.spawnedSwarm.transform.parent = transform;

            // Añadir ParticleSystem
            ParticleSystem ps = config.spawnedSwarm.AddComponent<ParticleSystem>();

            // Añadir InsectSwarm y configurar
            InsectSwarm swarmController = config.spawnedSwarm.AddComponent<InsectSwarm>();

            // Usar reflection para configurar campos privados si es necesario
            // O exponer métodos públicos en InsectSwarm para configuración
            swarmController.SetInsectType(config.insectType);
            swarmController.SetInsectCount(config.insectCount);
            swarmController.SetSwarmRadius(config.swarmRadius);
        }

        // Configurar el swarm si tiene el componente InsectSwarm
        InsectSwarm swarm = config.spawnedSwarm.GetComponent<InsectSwarm>();
        if (swarm != null)
        {
            swarm.SetInsectType(config.insectType);
            swarm.SetInsectCount(config.insectCount);
            swarm.SetSwarmRadius(config.swarmRadius);
        }
    }

    /// <summary>
    /// Actualiza el movimiento de enjambres que vagan por la zona
    /// </summary>
    private void UpdateWanderingSwarms()
    {
        for (int i = 0; i < swarms.Count; i++)
        {
            SwarmConfig config = swarms[i];

            if (!config.wanderInZone || config.spawnedSwarm == null) continue;

            // Obtener posición actual del enjambre
            Vector3 currentPos = config.spawnedSwarm.transform.position;
            Vector3 targetPos = wanderTargets[i];

            // Si llegó al objetivo, elegir uno nuevo
            if (Vector3.Distance(currentPos, targetPos) < 1f)
            {
                wanderTargets[i] = GetRandomPositionInZone();
                targetPos = wanderTargets[i];
            }

            // Mover hacia el objetivo
            Vector3 newPos = Vector3.MoveTowards(currentPos, targetPos, config.wanderSpeed * Time.deltaTime);
            config.spawnedSwarm.transform.position = newPos;
        }
    }

    /// <summary>
    /// Obtiene una posición aleatoria dentro de los límites de la zona
    /// </summary>
    private Vector3 GetRandomPositionInZone()
    {
        Vector3 size = zoneCollider.size;
        Vector3 center = zoneCollider.center;

        Vector3 randomOffset = new Vector3(
            Random.Range(-size.x / 2f, size.x / 2f),
            Random.Range(-size.y / 2f, size.y / 2f),
            Random.Range(-size.z / 2f, size.z / 2f)
        );

        return transform.position + center + randomOffset;
    }

    /// <summary>
    /// Añade un nuevo enjambre a la zona en tiempo de ejecución
    /// </summary>
    public void AddSwarm(SwarmConfig config)
    {
        swarms.Add(config);
        wanderTargets.Add(GetRandomPositionInZone());

        if (isActive)
        {
            SpawnSwarm(swarms.Count - 1);
        }
    }

    /// <summary>
    /// Elimina un enjambre de la zona
    /// </summary>
    public void RemoveSwarm(int index)
    {
        if (index < 0 || index >= swarms.Count) return;

        SwarmConfig config = swarms[index];
        if (config.spawnedSwarm != null)
        {
            Destroy(config.spawnedSwarm);
        }

        swarms.RemoveAt(index);
        wanderTargets.RemoveAt(index);
    }

    /// <summary>
    /// Activa manualmente la zona (sin trigger)
    /// </summary>
    public void ManualActivate()
    {
        ActivateZone();
    }

    /// <summary>
    /// Desactiva manualmente la zona
    /// </summary>
    public void ManualDeactivate()
    {
        DeactivateZone();
    }

    // Eventos de Trigger
    private void OnTriggerEnter(Collider other)
    {
        if (!activateOnPlayerEnter || alwaysActive) return;

        if (other.CompareTag(playerTag))
        {
            ActivateZone();
        }
    }

    private void OnTriggerExit(Collider other)
    {
        if (!activateOnPlayerEnter || alwaysActive) return;

        if (other.CompareTag(playerTag))
        {
            DeactivateZone();
        }
    }

    private void OnDestroy()
    {
        // Limpiar enjambres al destruir la zona
        foreach (var swarm in swarms)
        {
            if (swarm.spawnedSwarm != null)
            {
                Destroy(swarm.spawnedSwarm);
            }
        }
    }

    #if UNITY_EDITOR
    /// <summary>
    /// Visualiza la zona en el editor
    /// </summary>
    private void OnDrawGizmos()
    {
        BoxCollider col = GetComponent<BoxCollider>();
        if (col == null) return;

        // Dibujar caja de la zona
        Gizmos.color = gizmoColor;
        Gizmos.matrix = transform.localToWorldMatrix;
        Gizmos.DrawCube(col.center, col.size);

        // Dibujar wireframe
        Gizmos.color = new Color(gizmoColor.r, gizmoColor.g, gizmoColor.b, 1f);
        Gizmos.DrawWireCube(col.center, col.size);
    }

    private void OnDrawGizmosSelected()
    {
        BoxCollider col = GetComponent<BoxCollider>();
        if (col == null) return;

        // Dibujar posiciones de enjambres
        Gizmos.color = Color.yellow;
        foreach (var swarm in swarms)
        {
            Vector3 pos = transform.position + swarm.relativePosition;
            Gizmos.DrawWireSphere(pos, swarm.swarmRadius);

            // Dibujar línea desde el centro
            Gizmos.DrawLine(transform.position, pos);
        }

        // Dibujar etiqueta
        UnityEditor.Handles.Label(
            transform.position + Vector3.up * (col.size.y / 2f + 0.5f),
            $"Zona: {zoneDescription}\n{swarms.Count} enjambres"
        );
    }
    #endif
}
