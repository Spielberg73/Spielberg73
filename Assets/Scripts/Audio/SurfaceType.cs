using UnityEngine;

/// <summary>
/// Tipos de superficie para el sistema de pasos
/// Define los diferentes materiales que el jugador puede pisar
/// </summary>
public enum SurfaceType
{
    Concrete,    // Concreto/cemento
    Wood,        // Madera
    Metal,       // Metal
    Grass,       // Césped
    Gravel,      // Grava
    Sand,        // Arena
    Water,       // Agua (charcos)
    Mud,         // Barro
    Tile,        // Baldosas
    Carpet,      // Alfombra
    Snow,        // Nieve
    Glass,       // Vidrio
    Default      // Material por defecto
}

/// <summary>
/// Componente para identificar el tipo de superficie de un objeto
/// Añadir a objetos 3D para que el sistema detecte su material
/// </summary>
public class SurfaceIdentifier : MonoBehaviour
{
    [Header("Configuración de Superficie")]
    [SerializeField] private SurfaceType surfaceType = SurfaceType.Default;
    [SerializeField] private bool overridePhysicsMaterial = true;

    [Header("Modificadores de Audio")]
    [SerializeField] [Range(0f, 2f)] private float volumeMultiplier = 1f;
    [SerializeField] [Range(0.5f, 2f)] private float pitchMultiplier = 1f;

    [Header("Efectos Opcionales")]
    [SerializeField] private GameObject customParticleEffect;

    public SurfaceType GetSurfaceType() => surfaceType;
    public float GetVolumeMultiplier() => volumeMultiplier;
    public float GetPitchMultiplier() => pitchMultiplier;
    public GameObject GetCustomParticleEffect() => customParticleEffect;

    public void SetSurfaceType(SurfaceType type)
    {
        surfaceType = type;
    }

    // Visualización en el editor
    void OnDrawGizmosSelected()
    {
        Gizmos.color = GetColorForSurface(surfaceType);
        Gizmos.DrawWireCube(transform.position, transform.lossyScale);
    }

    private Color GetColorForSurface(SurfaceType type)
    {
        switch (type)
        {
            case SurfaceType.Concrete: return Color.gray;
            case SurfaceType.Wood: return new Color(0.6f, 0.3f, 0.1f);
            case SurfaceType.Metal: return Color.white;
            case SurfaceType.Grass: return Color.green;
            case SurfaceType.Gravel: return new Color(0.5f, 0.5f, 0.4f);
            case SurfaceType.Sand: return Color.yellow;
            case SurfaceType.Water: return Color.cyan;
            case SurfaceType.Mud: return new Color(0.4f, 0.2f, 0.1f);
            case SurfaceType.Tile: return new Color(0.8f, 0.8f, 0.9f);
            case SurfaceType.Carpet: return new Color(0.7f, 0.2f, 0.2f);
            case SurfaceType.Snow: return Color.white;
            case SurfaceType.Glass: return Color.cyan;
            default: return Color.magenta;
        }
    }
}
