using UnityEngine;

/// <summary>
/// Detecta el tipo de superficie bajo el jugador usando raycast
/// Prioriza SurfaceIdentifier, luego Physics Material, luego por tag
/// </summary>
public class SurfaceDetector : MonoBehaviour
{
    [Header("Configuración de Detección")]
    [SerializeField] private Transform detectionOrigin;
    [SerializeField] private float raycastDistance = 1.5f;
    [SerializeField] private LayerMask surfaceLayerMask = ~0;

    [Header("Fallbacks")]
    [SerializeField] private SurfaceType defaultSurface = SurfaceType.Concrete;
    [SerializeField] private bool usePhysicsMaterialMapping = true;
    [SerializeField] private bool useTagMapping = true;

    [Header("Debug")]
    [SerializeField] private bool showDebugRay = false;
    [SerializeField] private Color debugRayColor = Color.red;

    private SurfaceType currentSurface;
    private SurfaceIdentifier currentSurfaceIdentifier;
    private RaycastHit lastHit;

    public SurfaceType CurrentSurface => currentSurface;
    public SurfaceIdentifier CurrentSurfaceIdentifier => currentSurfaceIdentifier;
    public RaycastHit LastHit => lastHit;

    void Start()
    {
        if (detectionOrigin == null)
        {
            detectionOrigin = transform;
        }

        currentSurface = defaultSurface;
    }

    void Update()
    {
        DetectSurface();
    }

    /// <summary>
    /// Detecta la superficie bajo el jugador
    /// </summary>
    public void DetectSurface()
    {
        Vector3 origin = detectionOrigin.position;
        Vector3 direction = Vector3.down;

        // Debug visual
        if (showDebugRay)
        {
            Debug.DrawRay(origin, direction * raycastDistance, debugRayColor);
        }

        // Raycast hacia abajo
        if (Physics.Raycast(origin, direction, out lastHit, raycastDistance, surfaceLayerMask))
        {
            // Método 1: SurfaceIdentifier (más prioritario)
            SurfaceIdentifier identifier = lastHit.collider.GetComponent<SurfaceIdentifier>();
            if (identifier != null)
            {
                currentSurface = identifier.GetSurfaceType();
                currentSurfaceIdentifier = identifier;
                return;
            }

            // Método 2: Physics Material
            if (usePhysicsMaterialMapping && lastHit.collider.sharedMaterial != null)
            {
                SurfaceType surfaceFromMaterial = GetSurfaceFromPhysicsMaterial(lastHit.collider.sharedMaterial);
                if (surfaceFromMaterial != SurfaceType.Default)
                {
                    currentSurface = surfaceFromMaterial;
                    currentSurfaceIdentifier = null;
                    return;
                }
            }

            // Método 3: Tag
            if (useTagMapping)
            {
                SurfaceType surfaceFromTag = GetSurfaceFromTag(lastHit.collider.tag);
                if (surfaceFromTag != SurfaceType.Default)
                {
                    currentSurface = surfaceFromTag;
                    currentSurfaceIdentifier = null;
                    return;
                }
            }

            // Fallback: usar default
            currentSurface = defaultSurface;
            currentSurfaceIdentifier = null;
        }
        else
        {
            // No hay superficie detectada
            currentSurface = defaultSurface;
            currentSurfaceIdentifier = null;
        }
    }

    /// <summary>
    /// Mapea un Physics Material a un tipo de superficie
    /// </summary>
    private SurfaceType GetSurfaceFromPhysicsMaterial(PhysicMaterial material)
    {
        string materialName = material.name.ToLower();

        if (materialName.Contains("wood")) return SurfaceType.Wood;
        if (materialName.Contains("metal")) return SurfaceType.Metal;
        if (materialName.Contains("grass")) return SurfaceType.Grass;
        if (materialName.Contains("gravel")) return SurfaceType.Gravel;
        if (materialName.Contains("sand")) return SurfaceType.Sand;
        if (materialName.Contains("water")) return SurfaceType.Water;
        if (materialName.Contains("mud")) return SurfaceType.Mud;
        if (materialName.Contains("tile")) return SurfaceType.Tile;
        if (materialName.Contains("carpet")) return SurfaceType.Carpet;
        if (materialName.Contains("snow")) return SurfaceType.Snow;
        if (materialName.Contains("glass")) return SurfaceType.Glass;
        if (materialName.Contains("concrete") || materialName.Contains("cement")) return SurfaceType.Concrete;

        return SurfaceType.Default;
    }

    /// <summary>
    /// Mapea un tag a un tipo de superficie
    /// </summary>
    private SurfaceType GetSurfaceFromTag(string tag)
    {
        switch (tag.ToLower())
        {
            case "wood": return SurfaceType.Wood;
            case "metal": return SurfaceType.Metal;
            case "grass": return SurfaceType.Grass;
            case "gravel": return SurfaceType.Gravel;
            case "sand": return SurfaceType.Sand;
            case "water": return SurfaceType.Water;
            case "mud": return SurfaceType.Mud;
            case "tile": return SurfaceType.Tile;
            case "carpet": return SurfaceType.Carpet;
            case "snow": return SurfaceType.Snow;
            case "glass": return SurfaceType.Glass;
            case "concrete": return SurfaceType.Concrete;
            default: return SurfaceType.Default;
        }
    }

    /// <summary>
    /// Fuerza la detección inmediata de superficie
    /// </summary>
    public void ForceDetection()
    {
        DetectSurface();
    }

    /// <summary>
    /// Establece manualmente el tipo de superficie
    /// </summary>
    public void SetSurfaceType(SurfaceType type)
    {
        currentSurface = type;
    }

    // Métodos de configuración
    public void SetRaycastDistance(float distance)
    {
        raycastDistance = distance;
    }

    public void SetLayerMask(LayerMask mask)
    {
        surfaceLayerMask = mask;
    }

    // Debug visual en Scene view
    void OnDrawGizmosSelected()
    {
        if (detectionOrigin == null) return;

        Gizmos.color = Color.yellow;
        Gizmos.DrawLine(detectionOrigin.position,
                       detectionOrigin.position + Vector3.down * raycastDistance);

        if (Application.isPlaying && lastHit.collider != null)
        {
            Gizmos.color = Color.green;
            Gizmos.DrawSphere(lastHit.point, 0.1f);
        }
    }
}
