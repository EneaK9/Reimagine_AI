using UnityEngine;
using System;

namespace ReimagineAI
{
    /// <summary>
    /// Bridge for communication between Unity and Flutter via flutter_unity_widget
    /// </summary>
    public class FlutterBridge : MonoBehaviour
    {
        public static FlutterBridge Instance { get; private set; }

        // Events for different message types
        public static event Action OnStartScan;
        public static event Action OnStopScan;
        public static event Action OnExportRoom;
        public static event Action<string> OnLoadRoom;
        public static event Action<string> OnEditMaterial;
        public static event Action<string> OnSelectPart;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
            }
        }

        /// <summary>
        /// Send a message to Flutter
        /// </summary>
        public static void SendMessageToFlutter(string method, string data)
        {
            if (Instance == null)
            {
                Debug.LogWarning("FlutterBridge instance not found");
                return;
            }

            var message = new FlutterMessage
            {
                method = method,
                data = data
            };

            string json = JsonUtility.ToJson(message);
            
            // Use Unity's SendMessage to communicate with Flutter
            // The flutter_unity_widget listens on the "N/A" game object
            try
            {
                // This will be caught by flutter_unity_widget's native bridge
                UnityMessageManager.Instance?.SendMessageToFlutter(json);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"Failed to send message to Flutter: {e.Message}");
            }
        }

        /// <summary>
        /// Send scan progress update to Flutter
        /// </summary>
        public static void SendScanProgress(float progress)
        {
            SendMessageToFlutter("scanProgress", progress.ToString("F2"));
        }

        /// <summary>
        /// Notify Flutter that room was exported
        /// </summary>
        public static void SendRoomExported(string filePath)
        {
            SendMessageToFlutter("roomExported", filePath);
        }

        /// <summary>
        /// Notify Flutter that a part was selected
        /// </summary>
        public static void SendPartSelected(string partName)
        {
            SendMessageToFlutter("partSelected", partName);
        }

        /// <summary>
        /// Notify Flutter that an edit was applied
        /// </summary>
        public static void SendEditApplied(string editInfo)
        {
            SendMessageToFlutter("editApplied", editInfo);
        }

        /// <summary>
        /// Send error message to Flutter
        /// </summary>
        public static void SendError(string errorMessage)
        {
            SendMessageToFlutter("error", errorMessage);
        }

        /// <summary>
        /// Receive messages from Flutter (called by flutter_unity_widget)
        /// </summary>
        public void ReceiveMessage(string jsonMessage)
        {
            Debug.Log($"[FlutterBridge] Received message: {jsonMessage}");

            try
            {
                var msg = JsonUtility.FromJson<FlutterMessage>(jsonMessage);
                HandleMessage(msg);
            }
            catch (Exception e)
            {
                Debug.LogError($"[FlutterBridge] Failed to parse message: {e.Message}");
                SendError($"Failed to parse message: {e.Message}");
            }
        }

        private void HandleMessage(FlutterMessage msg)
        {
            switch (msg.method)
            {
                case "startScan":
                    Debug.Log("[FlutterBridge] Starting scan...");
                    OnStartScan?.Invoke();
                    break;

                case "stopScan":
                    Debug.Log("[FlutterBridge] Stopping scan...");
                    OnStopScan?.Invoke();
                    break;

                case "exportRoom":
                    Debug.Log("[FlutterBridge] Exporting room...");
                    OnExportRoom?.Invoke();
                    break;

                case "loadRoom":
                    Debug.Log($"[FlutterBridge] Loading room: {msg.data}");
                    OnLoadRoom?.Invoke(msg.data);
                    break;

                case "editMaterial":
                    Debug.Log($"[FlutterBridge] Editing material: {msg.data}");
                    OnEditMaterial?.Invoke(msg.data);
                    break;

                case "selectPart":
                    Debug.Log($"[FlutterBridge] Selecting part: {msg.data}");
                    OnSelectPart?.Invoke(msg.data);
                    break;

                default:
                    Debug.LogWarning($"[FlutterBridge] Unknown method: {msg.method}");
                    break;
            }
        }
    }

    [Serializable]
    public class FlutterMessage
    {
        public string method;
        public string data;
    }

    /// <summary>
    /// Placeholder for UnityMessageManager - will be provided by flutter_unity_widget
    /// </summary>
    public class UnityMessageManager
    {
        public static UnityMessageManager Instance { get; private set; }

        static UnityMessageManager()
        {
            Instance = new UnityMessageManager();
        }

        public void SendMessageToFlutter(string message)
        {
            // This will be overridden by flutter_unity_widget's native implementation
            // In editor, just log the message
#if UNITY_EDITOR
            Debug.Log($"[UnityMessageManager] Would send to Flutter: {message}");
#else
            // Native implementation will handle this
            SendUnityMessage(message);
#endif
        }

#if !UNITY_EDITOR
        [System.Runtime.InteropServices.DllImport("__Internal")]
        private static extern void SendUnityMessage(string message);
#endif
    }
}
