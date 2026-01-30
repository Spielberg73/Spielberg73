using UnityEngine;
using UnityEngine.InputSystem;
using TMPro;

/// <summary>
/// Sistema de interacción con objetos del mundo
/// Usa raycast para detectar objetos interactuables
/// </summary>
public class InteractionSystem : MonoBehaviour
{
    [Header("Configuración de Raycast")]
    [SerializeField] private Camera playerCamera;
    [SerializeField] private float interactionDistance = 3f;
    [SerializeField] private LayerMask interactableLayer = ~0; // Todas las capas por defecto

    [Header("Configuración de UI")]
    [SerializeField] private TextMeshProUGUI interactionText;
    [SerializeField] private GameObject interactionPromptUI;
    [SerializeField] private string interactKey = "E"; // Para mostrar en UI

    [Header("Configuración Visual")]
    [SerializeField] private bool showDebugRay = true;
    [SerializeField] private Color rayColor = Color.green;
    [SerializeField] private Color rayHitColor = Color.red;

    [Header("Efectos")]
    [SerializeField] private bool highlightInteractables = true;
    [SerializeField] private Color highlightColor = Color.yellow;

    private IInteractable currentInteractable;
    private GameObject currentInteractableObject;
    private Outline currentOutline;
    private PlayerInputActions inputActions;

    void Awake()
    {
        inputActions = new PlayerInputActions();
    }

    void OnEnable()
    {
        inputActions.Player.Enable();
        inputActions.Player.Interact.performed += OnInteract;
    }

    void OnDisable()
    {
        inputActions.Player.Interact.performed -= OnInteract;
        inputActions.Player.Disable();
    }

    void Start()
    {
        // Encontrar la cámara si no está asignada
        if (playerCamera == null)
        {
            playerCamera = Camera.main;
            if (playerCamera == null)
            {
                playerCamera = GetComponentInChildren<Camera>();
            }
        }

        // Ocultar el prompt al inicio
        if (interactionPromptUI != null)
        {
            interactionPromptUI.SetActive(false);
        }
    }

    void Update()
    {
        CheckForInteractable();
    }

    private void CheckForInteractable()
    {
        if (playerCamera == null) return;

        Ray ray = new Ray(playerCamera.transform.position, playerCamera.transform.forward);
        RaycastHit hit;

        // Debug ray
        if (showDebugRay)
        {
            Debug.DrawRay(ray.origin, ray.direction * interactionDistance,
                currentInteractable != null ? rayHitColor : rayColor);
        }

        // Raycast para detectar objetos
        if (Physics.Raycast(ray, out hit, interactionDistance, interactableLayer))
        {
            // Intentar obtener componente IInteractable
            IInteractable interactable = hit.collider.GetComponent<IInteractable>();

            if (interactable != null && interactable.CanInteract())
            {
                // Nuevo objeto interactuable detectado
                if (currentInteractable != interactable)
                {
                    SetCurrentInteractable(interactable, hit.collider.gameObject);
                }

                return;
            }
        }

        // No hay objeto interactuable
        if (currentInteractable != null)
        {
            ClearCurrentInteractable();
        }
    }

    private void SetCurrentInteractable(IInteractable interactable, GameObject obj)
    {
        // Limpiar anterior
        ClearCurrentInteractable();

        currentInteractable = interactable;
        currentInteractableObject = obj;

        // Mostrar UI
        ShowInteractionPrompt(interactable.GetInteractionPrompt());

        // Resaltar objeto
        if (highlightInteractables)
        {
            HighlightObject(obj);
        }
    }

    private void ClearCurrentInteractable()
    {
        currentInteractable = null;

        // Ocultar UI
        HideInteractionPrompt();

        // Quitar resaltado
        if (currentOutline != null)
        {
            Destroy(currentOutline);
            currentOutline = null;
        }

        currentInteractableObject = null;
    }

    private void OnInteract(InputAction.CallbackContext context)
    {
        if (currentInteractable != null && currentInteractable.CanInteract())
        {
            currentInteractable.Interact(gameObject);
            ClearCurrentInteractable();
        }
    }

    private void ShowInteractionPrompt(string message)
    {
        if (interactionPromptUI != null)
        {
            interactionPromptUI.SetActive(true);
        }

        if (interactionText != null)
        {
            interactionText.text = $"[{interactKey}] {message}";
        }
    }

    private void HideInteractionPrompt()
    {
        if (interactionPromptUI != null)
        {
            interactionPromptUI.SetActive(false);
        }
    }

    private void HighlightObject(GameObject obj)
    {
        // Añadir outline si no existe
        // Nota: Esto requiere un componente Outline. Si no lo tienes, comentar esta sección
        /*
        currentOutline = obj.GetComponent<Outline>();
        if (currentOutline == null)
        {
            currentOutline = obj.AddComponent<Outline>();
        }
        currentOutline.OutlineColor = highlightColor;
        currentOutline.OutlineWidth = 5f;
        currentOutline.enabled = true;
        */

        // Alternativa simple: cambiar el color del material (temporal)
        Renderer renderer = obj.GetComponent<Renderer>();
        if (renderer != null)
        {
            // Esta es una implementación simple, en producción usarías un sistema más sofisticado
            // Por ahora dejamos esto comentado para no modificar materiales
            // renderer.material.SetColor("_EmissionColor", highlightColor * 0.5f);
            // renderer.material.EnableKeyword("_EMISSION");
        }
    }

    // Configuración pública
    public void SetInteractionDistance(float distance)
    {
        interactionDistance = distance;
    }

    public float GetInteractionDistance()
    {
        return interactionDistance;
    }

    public IInteractable GetCurrentInteractable()
    {
        return currentInteractable;
    }

    // Debug info
    void OnGUI()
    {
        #if UNITY_EDITOR
        if (currentInteractable != null)
        {
            GUIStyle style = new GUIStyle();
            style.fontSize = 12;
            style.normal.textColor = Color.cyan;
            GUI.Label(new Rect(10, 50, 400, 20),
                $"Mirando: {currentInteractable.GetInteractionPrompt()}", style);
        }
        #endif
    }
}
