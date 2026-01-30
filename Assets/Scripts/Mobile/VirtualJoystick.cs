using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

/// <summary>
/// Joystick virtual para controles táctiles en móvil
/// Permite movimiento del jugador con el dedo
/// </summary>
public class VirtualJoystick : MonoBehaviour, IPointerDownHandler, IDragHandler, IPointerUpHandler
{
    [Header("Referencias UI")]
    [SerializeField] private RectTransform joystickBackground;
    [SerializeField] private RectTransform joystickHandle;

    [Header("Configuración")]
    [SerializeField] private float handleRange = 50f;
    [SerializeField] private float deadZone = 0.1f;
    [SerializeField] private bool resetOnRelease = true;
    [SerializeField] private bool dynamicJoystick = false; // Se mueve donde tocas

    [Header("Visual Feedback")]
    [SerializeField] private bool showDebugInfo = false;
    [SerializeField] private Color activeColor = new Color(1f, 1f, 1f, 0.8f);
    [SerializeField] private Color inactiveColor = new Color(1f, 1f, 1f, 0.3f);

    // Input
    private Vector2 inputVector;
    private Vector2 joystickStartPosition;
    private Canvas canvas;
    private Camera canvasCamera;
    private Image backgroundImage;
    private Image handleImage;

    public Vector2 InputVector => inputVector;
    public float Horizontal => inputVector.x;
    public float Vertical => inputVector.y;

    void Start()
    {
        // Obtener referencias
        canvas = GetComponentInParent<Canvas>();

        if (canvas != null)
        {
            canvasCamera = canvas.renderMode == RenderMode.ScreenSpaceOverlay ? null : canvas.worldCamera;
        }

        // Guardar posición inicial
        joystickStartPosition = joystickBackground.anchoredPosition;

        // Obtener componentes Image
        backgroundImage = joystickBackground.GetComponent<Image>();
        handleImage = joystickHandle.GetComponent<Image>();

        // Configurar alpha inicial
        SetAlpha(inactiveColor.a);
    }

    public void OnPointerDown(PointerEventData eventData)
    {
        if (dynamicJoystick)
        {
            // Mover joystick a donde se tocó
            Vector2 localPoint;
            RectTransformUtility.ScreenPointToLocalPointInRectangle(
                transform as RectTransform,
                eventData.position,
                canvasCamera,
                out localPoint
            );

            joystickBackground.anchoredPosition = localPoint;
        }

        OnDrag(eventData);
        SetAlpha(activeColor.a);
    }

    public void OnDrag(PointerEventData eventData)
    {
        Vector2 position;
        RectTransformUtility.ScreenPointToLocalPointInRectangle(
            joystickBackground,
            eventData.position,
            canvasCamera,
            out position
        );

        // Calcular dirección
        position = position / handleRange;

        // Limitar a círculo unitario
        inputVector = (position.magnitude > 1.0f) ? position.normalized : position;

        // Aplicar dead zone
        if (inputVector.magnitude < deadZone)
        {
            inputVector = Vector2.zero;
        }

        // Mover el handle
        joystickHandle.anchoredPosition = inputVector * handleRange;
    }

    public void OnPointerUp(PointerEventData eventData)
    {
        inputVector = Vector2.zero;

        if (resetOnRelease)
        {
            joystickHandle.anchoredPosition = Vector2.zero;
        }

        if (dynamicJoystick)
        {
            joystickBackground.anchoredPosition = joystickStartPosition;
        }

        SetAlpha(inactiveColor.a);
    }

    private void SetAlpha(float alpha)
    {
        if (backgroundImage != null)
        {
            Color bgColor = backgroundImage.color;
            bgColor.a = alpha;
            backgroundImage.color = bgColor;
        }

        if (handleImage != null)
        {
            Color handleColor = handleImage.color;
            handleColor.a = alpha;
            handleImage.color = handleColor;
        }
    }

    // Métodos públicos para configuración en runtime
    public void SetHandleRange(float range)
    {
        handleRange = range;
    }

    public void SetDeadZone(float zone)
    {
        deadZone = Mathf.Clamp01(zone);
    }

    public void SetDynamic(bool dynamic)
    {
        dynamicJoystick = dynamic;
    }

    // Debug
    void OnGUI()
    {
        if (!showDebugInfo) return;

        GUIStyle style = new GUIStyle();
        style.fontSize = 20;
        style.normal.textColor = Color.white;

        GUI.Label(new Rect(10, 100, 300, 30),
            $"Joystick: ({inputVector.x:F2}, {inputVector.y:F2})", style);
    }
}
