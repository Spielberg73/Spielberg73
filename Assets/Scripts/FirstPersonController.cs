using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Controlador de movimiento en primera persona con Input System
/// Incluye mecánicas profesionales estilo Half-Life: headbob, FOV dinámico, aceleración suave
/// Soporte completo para teclado/mouse y gamepad
/// </summary>
[RequireComponent(typeof(CharacterController))]
public class FirstPersonController : MonoBehaviour
{
    [Header("Configuración de Movimiento")]
    [SerializeField] private float walkSpeed = 5f;
    [SerializeField] private float sprintSpeed = 8f;
    [SerializeField] private float crouchSpeed = 2.5f;
    [SerializeField] private float acceleration = 10f;
    [SerializeField] private float deceleration = 10f;
    [SerializeField] private float airControl = 0.3f;

    [Header("Configuración de Salto")]
    [SerializeField] private float jumpHeight = 1.5f;
    [SerializeField] private float gravity = 20f;
    [SerializeField] private float jumpCooldown = 0.2f;

    [Header("Configuración de Cámara")]
    [SerializeField] private Transform cameraTransform;
    [SerializeField] private Camera playerCamera;
    [SerializeField] private float mouseSensitivity = 2f;
    [SerializeField] private float gamepadSensitivity = 3f;
    [SerializeField] private float lookXLimit = 85f;
    [SerializeField] private bool invertYAxis = false;

    [Header("Efectos Visuales - Head Bob")]
    [SerializeField] private bool enableHeadBob = true;
    [SerializeField] private float walkBobSpeed = 14f;
    [SerializeField] private float walkBobAmount = 0.05f;
    [SerializeField] private float sprintBobSpeed = 18f;
    [SerializeField] private float sprintBobAmount = 0.08f;

    [Header("Efectos Visuales - FOV")]
    [SerializeField] private bool enableDynamicFOV = true;
    [SerializeField] private float baseFOV = 60f;
    [SerializeField] private float sprintFOVIncrease = 10f;
    [SerializeField] private float fovChangeSpeed = 8f;

    [Header("Efectos Visuales - Inclinación")]
    [SerializeField] private bool enableCameraTilt = true;
    [SerializeField] private float tiltAmount = 2f;
    [SerializeField] private float tiltSpeed = 5f;

    [Header("Configuración de Agacharse")]
    [SerializeField] private bool enableCrouch = true;
    [SerializeField] private float crouchHeight = 1f;
    [SerializeField] private float standHeight = 2f;
    [SerializeField] private float crouchTransitionSpeed = 8f;

    // Input System
    private PlayerInputActions inputActions;
    private Vector2 moveInput;
    private Vector2 lookInput;
    private bool isSprinting;
    private bool isCrouching;
    private bool jumpPressed;

    // Componentes
    private CharacterController characterController;

    // Estado del movimiento
    private Vector3 currentVelocity;
    private Vector3 moveDirection;
    private float verticalVelocity;
    private bool isGrounded;
    private float lastJumpTime;

    // Cámara
    private float rotationX = 0;
    private float targetFOV;
    private float currentTilt;
    private Vector3 cameraStartPos;
    private float headBobTimer;

    void Awake()
    {
        inputActions = new PlayerInputActions();
        characterController = GetComponent<CharacterController>();
    }

    void OnEnable()
    {
        inputActions.Player.Enable();

        // Suscribirse a acciones
        inputActions.Player.Move.performed += ctx => moveInput = ctx.ReadValue<Vector2>();
        inputActions.Player.Move.canceled += ctx => moveInput = Vector2.zero;

        inputActions.Player.Look.performed += ctx => lookInput = ctx.ReadValue<Vector2>();
        inputActions.Player.Look.canceled += ctx => lookInput = Vector2.zero;

        inputActions.Player.Jump.performed += ctx => jumpPressed = true;
        inputActions.Player.Jump.canceled += ctx => jumpPressed = false;

        inputActions.Player.Sprint.performed += ctx => isSprinting = true;
        inputActions.Player.Sprint.canceled += ctx => isSprinting = false;

        inputActions.Player.Pause.performed += ctx => ToggleCursor();
    }

    void OnDisable()
    {
        inputActions.Player.Disable();
    }

    void Start()
    {
        // Bloquear cursor
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;

        // Encontrar cámara
        if (cameraTransform == null)
        {
            Camera mainCamera = Camera.main;
            if (mainCamera != null)
            {
                cameraTransform = mainCamera.transform;
                playerCamera = mainCamera;
                Debug.Log("FirstPersonController: Cámara encontrada automáticamente");
            }
            else
            {
                Debug.LogWarning("FirstPersonController: No se encontró cámara");
            }
        }

        if (playerCamera == null && cameraTransform != null)
        {
            playerCamera = cameraTransform.GetComponent<Camera>();
        }

        // Configuración inicial
        if (cameraTransform != null)
        {
            cameraStartPos = cameraTransform.localPosition;
        }

        if (playerCamera != null)
        {
            baseFOV = playerCamera.fieldOfView;
            targetFOV = baseFOV;
        }

        characterController.height = standHeight;
    }

    void Update()
    {
        CheckGrounded();
        HandleMovement();
        HandleRotation();
        HandleJump();
        HandleCrouch();
        HandleCameraEffects();
    }

    private void CheckGrounded()
    {
        // Verificar si está en el suelo con un pequeño raycast
        isGrounded = characterController.isGrounded;

        if (isGrounded && verticalVelocity < 0)
        {
            verticalVelocity = -2f;
        }
    }

    private void HandleMovement()
    {
        // Calcular velocidad objetivo
        float targetSpeed = isCrouching ? crouchSpeed : (isSprinting ? sprintSpeed : walkSpeed);

        // Dirección de movimiento basada en input
        Vector3 targetDirection = transform.right * moveInput.x + transform.forward * moveInput.y;

        // Aceleración/deceleración suave
        float accelRate = (moveInput.magnitude > 0.1f) ? acceleration : deceleration;

        if (!isGrounded)
        {
            accelRate *= airControl;
        }

        // Interpolar hacia la velocidad objetivo
        Vector3 targetVelocity = targetDirection.normalized * targetSpeed * moveInput.magnitude;
        currentVelocity = Vector3.Lerp(currentVelocity, targetVelocity, accelRate * Time.deltaTime);

        // Aplicar movimiento horizontal
        characterController.Move(currentVelocity * Time.deltaTime);

        // Aplicar gravedad
        verticalVelocity -= gravity * Time.deltaTime;
        characterController.Move(new Vector3(0, verticalVelocity, 0) * Time.deltaTime);
    }

    private void HandleRotation()
    {
        if (cameraTransform == null) return;

        // Determinar sensibilidad según dispositivo de entrada
        float sensitivity = (Gamepad.current != null && lookInput.magnitude > 0.5f)
            ? gamepadSensitivity
            : mouseSensitivity;

        // Rotación horizontal del cuerpo
        float mouseX = lookInput.x * sensitivity;
        transform.Rotate(Vector3.up * mouseX);

        // Rotación vertical de la cámara
        float mouseY = lookInput.y * sensitivity;
        if (invertYAxis) mouseY = -mouseY;

        rotationX -= mouseY;
        rotationX = Mathf.Clamp(rotationX, -lookXLimit, lookXLimit);
        cameraTransform.localRotation = Quaternion.Euler(rotationX, 0, currentTilt);
    }

    private void HandleJump()
    {
        if (jumpPressed && isGrounded && Time.time > lastJumpTime + jumpCooldown)
        {
            verticalVelocity = Mathf.Sqrt(jumpHeight * 2f * gravity);
            lastJumpTime = Time.time;
            jumpPressed = false;
        }
    }

    private void HandleCrouch()
    {
        if (!enableCrouch) return;

        // Transición suave de altura
        float targetHeight = isCrouching ? crouchHeight : standHeight;
        characterController.height = Mathf.Lerp(
            characterController.height,
            targetHeight,
            crouchTransitionSpeed * Time.deltaTime
        );

        // Ajustar centro del controlador
        characterController.center = new Vector3(0, characterController.height / 2f, 0);
    }

    private void HandleCameraEffects()
    {
        if (cameraTransform == null) return;

        // Head Bob
        if (enableHeadBob && isGrounded && moveInput.magnitude > 0.1f)
        {
            ApplyHeadBob();
        }
        else
        {
            ResetHeadBob();
        }

        // FOV Dinámico
        if (enableDynamicFOV && playerCamera != null)
        {
            ApplyDynamicFOV();
        }

        // Inclinación de cámara
        if (enableCameraTilt)
        {
            ApplyCameraTilt();
        }
    }

    private void ApplyHeadBob()
    {
        float bobSpeed = isSprinting ? sprintBobSpeed : walkBobSpeed;
        float bobAmount = isSprinting ? sprintBobAmount : walkBobAmount;

        headBobTimer += Time.deltaTime * bobSpeed;

        float bobOffsetY = Mathf.Sin(headBobTimer) * bobAmount;
        float bobOffsetX = Mathf.Cos(headBobTimer * 0.5f) * bobAmount * 0.5f;

        Vector3 targetPos = cameraStartPos + new Vector3(bobOffsetX, bobOffsetY, 0);
        cameraTransform.localPosition = Vector3.Lerp(
            cameraTransform.localPosition,
            targetPos,
            Time.deltaTime * 10f
        );
    }

    private void ResetHeadBob()
    {
        headBobTimer = 0;
        cameraTransform.localPosition = Vector3.Lerp(
            cameraTransform.localPosition,
            cameraStartPos,
            Time.deltaTime * 5f
        );
    }

    private void ApplyDynamicFOV()
    {
        targetFOV = baseFOV + (isSprinting && moveInput.magnitude > 0.5f ? sprintFOVIncrease : 0);
        playerCamera.fieldOfView = Mathf.Lerp(
            playerCamera.fieldOfView,
            targetFOV,
            fovChangeSpeed * Time.deltaTime
        );
    }

    private void ApplyCameraTilt()
    {
        float targetTilt = -moveInput.x * tiltAmount;
        currentTilt = Mathf.Lerp(currentTilt, targetTilt, tiltSpeed * Time.deltaTime);
    }

    private void ToggleCursor()
    {
        if (Cursor.lockState == CursorLockMode.Locked)
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }
        else
        {
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
        }
    }

    // Métodos públicos
    public bool IsGrounded() => isGrounded;
    public bool IsSprinting() => isSprinting;
    public bool IsCrouching() => isCrouching;
    public Vector3 GetVelocity() => currentVelocity;
    public float GetSpeed() => currentVelocity.magnitude;

    public void SetSensitivity(float sensitivity)
    {
        mouseSensitivity = sensitivity;
    }

    public void SetFOV(float fov)
    {
        baseFOV = fov;
        if (playerCamera != null)
        {
            playerCamera.fieldOfView = fov;
        }
    }

    void OnValidate()
    {
        if (characterController == null)
        {
            characterController = GetComponent<CharacterController>();
        }
    }
}
