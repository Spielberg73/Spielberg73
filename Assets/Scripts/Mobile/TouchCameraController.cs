using UnityEngine;
using UnityEngine.EventSystems;

/// <summary>
/// Control de cámara táctil para móvil
/// Permite rotar la cámara deslizando el dedo por la pantalla
/// </summary>
public class TouchCameraController : MonoBehaviour, IDragHandler, IPointerDownHandler, IPointerUpHandler
{
    [Header("Configuración de Sensibilidad")]
    [SerializeField] private float touchSensitivityX = 2f;
    [SerializeField] private float touchSensitivityY = 2f;
    [SerializeField] private bool invertY = false;

    [Header("Límites de Rotación")]
    [SerializeField] private float minVerticalAngle = -80f;
    [SerializeField] private float maxVerticalAngle = 80f;

    [Header("Suavizado")]
    [SerializeField] private bool smoothRotation = true;
    [SerializeField] private float smoothSpeed = 10f;

    [Header("Detección Multi-Touch")]
    [SerializeField] private bool allowMultiTouch = true;
    [SerializeField] private int touchFingerId = -1; // -1 = cualquier dedo

    // Estado
    private Vector2 lookInput;
    private Vector2 targetLookInput;
    private bool isDragging = false;
    private int currentFingerId = -1;

    public Vector2 LookInput => lookInput;
    public float LookX => lookInput.x;
    public float LookY => lookInput.y;
    public bool IsDragging => isDragging;

    void Update()
    {
        // Suavizar input
        if (smoothRotation)
        {
            lookInput = Vector2.Lerp(lookInput, targetLookInput, smoothSpeed * Time.deltaTime);
        }
        else
        {
            lookInput = targetLookInput;
        }

        // Reset si no estamos arrastrando
        if (!isDragging)
        {
            targetLookInput = Vector2.zero;
        }
    }

    public void OnPointerDown(PointerEventData eventData)
    {
        // Verificar si podemos usar este toque
        if (!allowMultiTouch && currentFingerId != -1)
            return;

        if (touchFingerId != -1 && eventData.pointerId != touchFingerId)
            return;

        currentFingerId = eventData.pointerId;
        isDragging = true;
    }

    public void OnDrag(PointerEventData eventData)
    {
        // Verificar que sea el dedo correcto
        if (eventData.pointerId != currentFingerId)
            return;

        // Calcular delta
        Vector2 delta = eventData.delta;

        // Aplicar sensibilidad
        float lookX = delta.x * touchSensitivityX * 0.1f;
        float lookY = delta.y * touchSensitivityY * 0.1f;

        // Invertir Y si está configurado
        if (invertY)
        {
            lookY = -lookY;
        }

        targetLookInput = new Vector2(lookX, lookY);
    }

    public void OnPointerUp(PointerEventData eventData)
    {
        // Solo reset si es nuestro dedo
        if (eventData.pointerId != currentFingerId)
            return;

        isDragging = false;
        currentFingerId = -1;
        targetLookInput = Vector2.zero;
    }

    // Métodos públicos para configuración
    public void SetSensitivity(float sensitivityX, float sensitivityY)
    {
        touchSensitivityX = sensitivityX;
        touchSensitivityY = sensitivityY;
    }

    public void SetInvertY(bool invert)
    {
        invertY = invert;
    }

    public void ResetInput()
    {
        lookInput = Vector2.zero;
        targetLookInput = Vector2.zero;
        isDragging = false;
        currentFingerId = -1;
    }

    // Debug
    void OnGUI()
    {
        #if UNITY_EDITOR
        if (isDragging)
        {
            GUIStyle style = new GUIStyle();
            style.fontSize = 20;
            style.normal.textColor = Color.cyan;
            GUI.Label(new Rect(10, 130, 300, 30),
                $"Camera Touch: ({lookInput.x:F2}, {lookInput.y:F2})", style);
        }
        #endif
    }
}
