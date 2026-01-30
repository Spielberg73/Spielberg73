using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Gestor de controles móviles
/// Activa/desactiva controles táctiles y coordina el input entre PC y móvil
/// </summary>
public class MobileControlsManager : MonoBehaviour
{
    [Header("Activar Controles Móviles")]
    [SerializeField] private bool enableMobileControls = false;
    [SerializeField] private bool autoDetectPlatform = true;

    [Header("Referencias de Controles")]
    [SerializeField] private GameObject mobileControlsUI;
    [SerializeField] private VirtualJoystick movementJoystick;
    [SerializeField] private TouchCameraController touchCamera;

    [Header("Referencias de Botones")]
    [SerializeField] private TouchButton jumpButton;
    [SerializeField] private TouchButton sprintButton;
    [SerializeField] private TouchButton flashlightButton;
    [SerializeField] private TouchButton interactButton;

    [Header("Configuración")]
    [SerializeField] private bool hideInEditor = true;
    [SerializeField] private bool showDebugInfo = false;

    // Estado
    private bool isMobilePlatform = false;
    private bool controlsActive = false;

    // Input público para otros scripts
    public Vector2 MovementInput { get; private set; }
    public Vector2 LookInput { get; private set; }
    public bool JumpPressed { get; private set; }
    public bool SprintPressed { get; private set; }
    public bool FlashlightPressed { get; private set; }
    public bool InteractPressed { get; private set; }

    // Propiedades públicas
    public bool IsMobileControlsEnabled => controlsActive;
    public bool IsMobilePlatform => isMobilePlatform;

    void Start()
    {
        // Detectar plataforma
        DetectPlatform();

        // Configurar controles
        SetupControls();

        // Conectar eventos de botones
        ConnectButtonEvents();

        // Activar/desactivar según configuración
        UpdateControlsVisibility();
    }

    void Update()
    {
        if (!controlsActive) return;

        // Actualizar inputs desde controles móviles
        UpdateMobileInput();
    }

    private void DetectPlatform()
    {
        if (autoDetectPlatform)
        {
            #if UNITY_ANDROID || UNITY_IOS
                isMobilePlatform = true;
            #elif UNITY_EDITOR
                isMobilePlatform = false;
            #else
                // En build, detectar por Application
                isMobilePlatform = Application.isMobilePlatform;
            #endif
        }
        else
        {
            isMobilePlatform = enableMobileControls;
        }

        Debug.Log($"[MobileControls] Platform: {Application.platform}, IsMobile: {isMobilePlatform}");
    }

    private void SetupControls()
    {
        // Buscar componentes si no están asignados
        if (mobileControlsUI == null)
        {
            mobileControlsUI = GameObject.Find("MobileControlsUI");
        }

        if (movementJoystick == null)
        {
            movementJoystick = FindObjectOfType<VirtualJoystick>();
        }

        if (touchCamera == null)
        {
            touchCamera = FindObjectOfType<TouchCameraController>();
        }

        // Buscar botones
        if (jumpButton == null)
        {
            GameObject jumpObj = GameObject.Find("JumpButton");
            if (jumpObj != null) jumpButton = jumpObj.GetComponent<TouchButton>();
        }

        if (sprintButton == null)
        {
            GameObject sprintObj = GameObject.Find("SprintButton");
            if (sprintObj != null) sprintButton = sprintObj.GetComponent<TouchButton>();
        }

        if (flashlightButton == null)
        {
            GameObject flashObj = GameObject.Find("FlashlightButton");
            if (flashObj != null) flashlightButton = flashObj.GetComponent<TouchButton>();
        }

        if (interactButton == null)
        {
            GameObject interactObj = GameObject.Find("InteractButton");
            if (interactObj != null) interactButton = interactObj.GetComponent<TouchButton>();
        }
    }

    private void ConnectButtonEvents()
    {
        if (jumpButton != null)
        {
            jumpButton.OnButtonDown.AddListener(() => JumpPressed = true);
            jumpButton.OnButtonUp.AddListener(() => JumpPressed = false);
        }

        if (sprintButton != null)
        {
            sprintButton.OnButtonDown.AddListener(() => SprintPressed = true);
            sprintButton.OnButtonUp.AddListener(() => SprintPressed = false);
        }

        if (flashlightButton != null)
        {
            flashlightButton.OnButtonDown.AddListener(() => FlashlightPressed = true);
            flashlightButton.OnButtonUp.AddListener(() => FlashlightPressed = false);
        }

        if (interactButton != null)
        {
            interactButton.OnButtonDown.AddListener(() => InteractPressed = true);
            interactButton.OnButtonUp.AddListener(() => InteractPressed = false);
        }
    }

    private void UpdateMobileInput()
    {
        // Movimiento desde joystick
        if (movementJoystick != null)
        {
            MovementInput = movementJoystick.InputVector;
        }

        // Cámara desde touch
        if (touchCamera != null)
        {
            LookInput = touchCamera.LookInput;
        }
    }

    private void UpdateControlsVisibility()
    {
        // Determinar si activar controles
        bool shouldActivate = enableMobileControls;

        if (autoDetectPlatform)
        {
            shouldActivate = isMobilePlatform;
        }

        #if UNITY_EDITOR
        if (hideInEditor)
        {
            shouldActivate = false;
        }
        #endif

        controlsActive = shouldActivate;

        // Activar/desactivar UI
        if (mobileControlsUI != null)
        {
            mobileControlsUI.SetActive(controlsActive);
        }

        Debug.Log($"[MobileControls] Active: {controlsActive}");
    }

    // Métodos públicos para control manual
    public void EnableMobileControls(bool enable)
    {
        enableMobileControls = enable;
        UpdateControlsVisibility();
    }

    public void SetAutoDetect(bool auto)
    {
        autoDetectPlatform = auto;
        DetectPlatform();
        UpdateControlsVisibility();
    }

    public void ResetAllInputs()
    {
        MovementInput = Vector2.zero;
        LookInput = Vector2.zero;
        JumpPressed = false;
        SprintPressed = false;
        FlashlightPressed = false;
        InteractPressed = false;

        if (movementJoystick != null)
        {
            movementJoystick.OnPointerUp(null);
        }

        if (touchCamera != null)
        {
            touchCamera.ResetInput();
        }
    }

    // Métodos para obtener input (compatibilidad con Input System)
    public Vector2 GetMovementInput()
    {
        return controlsActive ? MovementInput : Vector2.zero;
    }

    public Vector2 GetLookInput()
    {
        return controlsActive ? LookInput : Vector2.zero;
    }

    public bool GetJumpInput()
    {
        return controlsActive && JumpPressed;
    }

    public bool GetSprintInput()
    {
        return controlsActive && SprintPressed;
    }

    public bool GetFlashlightInput()
    {
        bool result = controlsActive && FlashlightPressed;
        if (result) FlashlightPressed = false; // Consumir input
        return result;
    }

    public bool GetInteractInput()
    {
        bool result = controlsActive && InteractPressed;
        if (result) InteractPressed = false; // Consumir input
        return result;
    }

    // Debug
    void OnGUI()
    {
        if (!showDebugInfo || !controlsActive) return;

        GUIStyle style = new GUIStyle();
        style.fontSize = 16;
        style.normal.textColor = Color.yellow;

        int y = 160;
        GUI.Label(new Rect(10, y, 300, 25), $"Mobile Controls: ACTIVE", style);
        y += 25;
        GUI.Label(new Rect(10, y, 300, 25), $"Movement: ({MovementInput.x:F2}, {MovementInput.y:F2})", style);
        y += 25;
        GUI.Label(new Rect(10, y, 300, 25), $"Look: ({LookInput.x:F2}, {LookInput.y:F2})", style);
        y += 25;
        GUI.Label(new Rect(10, y, 300, 25), $"Jump: {JumpPressed} | Sprint: {SprintPressed}", style);
        y += 25;
        GUI.Label(new Rect(10, y, 300, 25), $"Flashlight: {FlashlightPressed} | Interact: {InteractPressed}", style);
    }

    // Cleanup
    void OnDestroy()
    {
        // Desconectar eventos
        if (jumpButton != null) jumpButton.OnButtonDown.RemoveAllListeners();
        if (sprintButton != null) sprintButton.OnButtonDown.RemoveAllListeners();
        if (flashlightButton != null) flashlightButton.OnButtonDown.RemoveAllListeners();
        if (interactButton != null) interactButton.OnButtonDown.RemoveAllListeners();
    }

    // Método para recargar configuración en runtime (Inspector)
    void OnValidate()
    {
        if (Application.isPlaying)
        {
            UpdateControlsVisibility();
        }
    }
}
