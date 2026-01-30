using UnityEngine;

/// <summary>
/// Batería recogible que el jugador puede recoger para recargar su linterna
/// </summary>
public class BatteryPickup : MonoBehaviour, IInteractable
{
    [Header("Configuración de Batería")]
    [SerializeField] private float batteryAmount = 25f;
    [SerializeField] private string interactionPrompt = "Recoger batería";

    [Header("Efectos Visuales")]
    [SerializeField] private bool rotateObject = true;
    [SerializeField] private float rotationSpeed = 50f;
    [SerializeField] private bool bobUpDown = true;
    [SerializeField] private float bobSpeed = 2f;
    [SerializeField] private float bobHeight = 0.2f;

    [Header("Efectos de Audio")]
    [SerializeField] private AudioClip pickupSound;
    [SerializeField] private float pickupVolume = 0.7f;

    [Header("Efectos de Partículas")]
    [SerializeField] private GameObject pickupEffect;

    private Vector3 startPosition;
    private bool canBePickedUp = true;

    void Start()
    {
        startPosition = transform.position;

        // Asegurar que tiene un collider para detección
        if (GetComponent<Collider>() == null)
        {
            SphereCollider collider = gameObject.AddComponent<SphereCollider>();
            collider.isTrigger = true;
            collider.radius = 0.5f;
        }
    }

    void Update()
    {
        if (!canBePickedUp) return;

        // Rotación
        if (rotateObject)
        {
            transform.Rotate(Vector3.up, rotationSpeed * Time.deltaTime);
        }

        // Movimiento de flotación arriba/abajo
        if (bobUpDown)
        {
            float newY = startPosition.y + Mathf.Sin(Time.time * bobSpeed) * bobHeight;
            transform.position = new Vector3(transform.position.x, newY, transform.position.z);
        }
    }

    public string GetInteractionPrompt()
    {
        return $"{interactionPrompt} (+{batteryAmount}%)";
    }

    public void Interact(GameObject player)
    {
        if (!canBePickedUp) return;

        // Buscar el BatterySystem en el jugador
        BatterySystem batterySystem = player.GetComponentInChildren<BatterySystem>();

        if (batterySystem != null)
        {
            batterySystem.AddBattery(batteryAmount);
            PlayPickupEffects(player);
            Destroy(gameObject);
        }
        else
        {
            Debug.LogWarning("El jugador no tiene un BatterySystem!");
        }
    }

    public bool CanInteract()
    {
        return canBePickedUp;
    }

    public Transform GetTransform()
    {
        return transform;
    }

    private void PlayPickupEffects(GameObject player)
    {
        // Sonido
        if (pickupSound != null)
        {
            AudioSource.PlayClipAtPoint(pickupSound, transform.position, pickupVolume);
        }

        // Efecto de partículas
        if (pickupEffect != null)
        {
            Instantiate(pickupEffect, transform.position, Quaternion.identity);
        }
    }

    // Alternativa: recoger al tocar (sin necesidad de presionar E)
    void OnTriggerEnter(Collider other)
    {
        // Descomentar si quieres recogida automática al tocar
        /*
        if (other.CompareTag("Player"))
        {
            Interact(other.gameObject);
        }
        */
    }

    // Visualización en el editor
    void OnDrawGizmos()
    {
        Gizmos.color = Color.yellow;
        Gizmos.DrawWireSphere(transform.position, 0.5f);

        Gizmos.color = Color.cyan;
        Gizmos.DrawLine(transform.position, transform.position + Vector3.up * 0.5f);
    }

    // Configuración pública
    public void SetBatteryAmount(float amount)
    {
        batteryAmount = amount;
    }

    public float GetBatteryAmount()
    {
        return batteryAmount;
    }
}
