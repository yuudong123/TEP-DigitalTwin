using UnityEngine;
using UnityEngine.InputSystem;

namespace TEP.DigitalTwin
{
    [RequireComponent(typeof(Camera))]
    public sealed class FlyCameraController : MonoBehaviour
    {
        [SerializeField, Min(0.1f)] private float moveSpeed = 6f;
        [SerializeField, Min(1f)] private float boostMultiplier = 2.5f;
        [SerializeField, Min(0.01f)] private float lookSensitivity = 0.12f;
        [SerializeField] private bool requireRightMouseForLook = true;

        private float yaw;
        private float pitch;

        private void Awake()
        {
            var angles = transform.eulerAngles;
            yaw = angles.y;
            pitch = NormalizeAngle(angles.x);
        }

        private void Update()
        {
            var keyboard = Keyboard.current;
            if (keyboard != null) Move(keyboard);

            var mouse = Mouse.current;
            if (mouse != null) Look(mouse);
        }

        private void Move(Keyboard keyboard)
        {
            var input = Vector3.zero;
            if (keyboard.wKey.isPressed) input += transform.forward;
            if (keyboard.sKey.isPressed) input -= transform.forward;
            if (keyboard.dKey.isPressed) input += transform.right;
            if (keyboard.aKey.isPressed) input -= transform.right;
            if (keyboard.eKey.isPressed) input += Vector3.up;
            if (keyboard.qKey.isPressed) input -= Vector3.up;

            var boosting = keyboard.leftShiftKey.isPressed || keyboard.rightShiftKey.isPressed;
            var speed = moveSpeed * (boosting ? boostMultiplier : 1f);
            transform.position += Vector3.ClampMagnitude(input, 1f) * (speed * Time.unscaledDeltaTime);
        }

        private void Look(Mouse mouse)
        {
            var looking = !requireRightMouseForLook || mouse.rightButton.isPressed;
            if (!looking)
            {
                if (Cursor.lockState != CursorLockMode.None)
                {
                    Cursor.lockState = CursorLockMode.None;
                    Cursor.visible = true;
                }
                return;
            }

            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
            var delta = mouse.delta.ReadValue() * lookSensitivity;
            yaw += delta.x;
            pitch = Mathf.Clamp(pitch - delta.y, -85f, 85f);
            transform.rotation = Quaternion.Euler(pitch, yaw, 0f);
        }

        private void OnDisable()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }

        private static float NormalizeAngle(float angle) => angle > 180f ? angle - 360f : angle;
    }
}
