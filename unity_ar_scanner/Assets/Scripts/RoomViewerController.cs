using UnityEngine;
using System;
using System.Collections;
using System.IO;

namespace ReimagineAI
{
    /// <summary>
    /// Controls 3D room viewing with orbit camera and part selection
    /// </summary>
    public class RoomViewerController : MonoBehaviour
    {
        [Header("View Components")]
        [SerializeField] private Camera viewCamera;
        [SerializeField] private Transform roomContainer;
        [SerializeField] private Light sceneLight;
        
        [Header("Camera Settings")]
        [SerializeField] private float rotationSpeed = 5f;
        [SerializeField] private float zoomSpeed = 2f;
        [SerializeField] private float panSpeed = 0.5f;
        [SerializeField] private float minZoom = 2f;
        [SerializeField] private float maxZoom = 20f;
        
        [Header("Selection")]
        [SerializeField] private Material selectionHighlightMaterial;
        [SerializeField] private Color highlightColor = new Color(0f, 0.8f, 1f, 0.5f);
        
        [Header("Material Editor")]
        [SerializeField] private MaterialEditor materialEditor;
        
        private GameObject loadedRoom;
        private string currentRoomPath;
        private Transform cameraTarget;
        private float currentZoom = 10f;
        private Vector2 currentRotation = new Vector2(30f, 45f);
        
        // Touch handling
        private Vector2 lastTouchPosition;
        private bool isDragging = false;
        private int touchCount = 0;
        private float lastPinchDistance = 0f;
        
        // Selection
        private GameObject selectedPart;
        private Material originalMaterial;
        
        private void OnEnable()
        {
            FlutterBridge.OnLoadRoom += LoadRoom;
            FlutterBridge.OnSelectPart += SelectPartByName;
        }
        
        private void OnDisable()
        {
            FlutterBridge.OnLoadRoom -= LoadRoom;
            FlutterBridge.OnSelectPart -= SelectPartByName;
        }
        
        private void Start()
        {
            // Initialize camera target
            if (cameraTarget == null)
            {
                var targetObj = new GameObject("CameraTarget");
                cameraTarget = targetObj.transform;
                cameraTarget.SetParent(transform);
                cameraTarget.localPosition = Vector3.zero;
            }
            
            UpdateCameraPosition();
        }
        
        private void Update()
        {
            HandleInput();
        }
        
        /// <summary>
        /// Load a room model from file path
        /// </summary>
        public void LoadRoom(string filePath)
        {
            Debug.Log($"[RoomViewer] Loading room from: {filePath}");
            
            if (string.IsNullOrEmpty(filePath))
            {
                FlutterBridge.SendError("No file path provided");
                return;
            }
            
            if (!File.Exists(filePath))
            {
                FlutterBridge.SendError($"File not found: {filePath}");
                return;
            }
            
            // Unload previous room
            if (loadedRoom != null)
            {
                Destroy(loadedRoom);
            }
            
            StartCoroutine(LoadRoomAsync(filePath));
        }
        
        private IEnumerator LoadRoomAsync(string filePath)
        {
            currentRoomPath = filePath;
            
            // Determine file type
            string extension = Path.GetExtension(filePath).ToLower();
            
            if (extension == ".glb" || extension == ".gltf")
            {
                // Load glTF/GLB
                yield return LoadGLTF(filePath);
            }
            else if (extension == ".obj")
            {
                // Load OBJ
                yield return LoadOBJ(filePath);
            }
            else
            {
                FlutterBridge.SendError($"Unsupported file format: {extension}");
                yield break;
            }
            
            if (loadedRoom != null)
            {
                // Parent to container
                loadedRoom.transform.SetParent(roomContainer);
                loadedRoom.transform.localPosition = Vector3.zero;
                loadedRoom.transform.localRotation = Quaternion.identity;
                
                // Center camera on room
                CenterCameraOnRoom();
                
                // Setup material editor
                if (materialEditor != null)
                {
                    materialEditor.SetTargetRoom(loadedRoom);
                }
                
                FlutterBridge.SendMessageToFlutter("roomLoaded", filePath);
                Debug.Log("[RoomViewer] Room loaded successfully");
            }
        }
        
        private IEnumerator LoadGLTF(string filePath)
        {
            // Note: In a real implementation, you would use a glTF loader like GLTFUtility
            // For now, we'll create a placeholder or use Unity's native glTF support (if available)
            
            Debug.Log($"[RoomViewer] Loading glTF: {filePath}");
            
            // Try using GLTFUtility or similar plugin
            // This is a placeholder - actual implementation depends on the glTF loader used
            
#if UNITY_2020_2_OR_NEWER
            // Unity 2020.2+ has some native glTF support
            // But for full support, GLTFUtility or UnityGLTF is recommended
#endif
            
            // Placeholder: Create a simple cube as fallback
            loadedRoom = GameObject.CreatePrimitive(PrimitiveType.Cube);
            loadedRoom.name = "LoadedRoom";
            
            // Add note that glTF loader needs to be configured
            Debug.LogWarning("[RoomViewer] glTF loader not configured. Using placeholder. " +
                           "Install GLTFUtility package for full glTF support.");
            
            yield return null;
        }
        
        private IEnumerator LoadOBJ(string filePath)
        {
            Debug.Log($"[RoomViewer] Loading OBJ: {filePath}");
            
            // Simple OBJ loader
            try
            {
                string[] lines = File.ReadAllLines(filePath);
                
                var vertices = new System.Collections.Generic.List<Vector3>();
                var normals = new System.Collections.Generic.List<Vector3>();
                var uvs = new System.Collections.Generic.List<Vector2>();
                var triangles = new System.Collections.Generic.List<int>();
                
                foreach (string line in lines)
                {
                    if (line.StartsWith("v "))
                    {
                        var parts = line.Substring(2).Split(' ');
                        vertices.Add(new Vector3(
                            float.Parse(parts[0]),
                            float.Parse(parts[1]),
                            float.Parse(parts[2])
                        ));
                    }
                    else if (line.StartsWith("vn "))
                    {
                        var parts = line.Substring(3).Split(' ');
                        normals.Add(new Vector3(
                            float.Parse(parts[0]),
                            float.Parse(parts[1]),
                            float.Parse(parts[2])
                        ));
                    }
                    else if (line.StartsWith("vt "))
                    {
                        var parts = line.Substring(3).Split(' ');
                        uvs.Add(new Vector2(
                            float.Parse(parts[0]),
                            float.Parse(parts[1])
                        ));
                    }
                    else if (line.StartsWith("f "))
                    {
                        var parts = line.Substring(2).Split(' ');
                        // Simple triangulation (assumes faces are triangles or quads)
                        for (int i = 1; i < parts.Length - 1; i++)
                        {
                            triangles.Add(ParseFaceIndex(parts[0]) - 1);
                            triangles.Add(ParseFaceIndex(parts[i]) - 1);
                            triangles.Add(ParseFaceIndex(parts[i + 1]) - 1);
                        }
                    }
                }
                
                // Create mesh
                var mesh = new Mesh();
                mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
                mesh.vertices = vertices.ToArray();
                if (normals.Count == vertices.Count)
                    mesh.normals = normals.ToArray();
                if (uvs.Count == vertices.Count)
                    mesh.uv = uvs.ToArray();
                mesh.triangles = triangles.ToArray();
                
                if (normals.Count != vertices.Count)
                    mesh.RecalculateNormals();
                
                mesh.RecalculateBounds();
                
                // Create game object
                loadedRoom = new GameObject("LoadedRoom");
                var meshFilter = loadedRoom.AddComponent<MeshFilter>();
                var meshRenderer = loadedRoom.AddComponent<MeshRenderer>();
                
                meshFilter.mesh = mesh;
                meshRenderer.material = new Material(Shader.Find("Standard"));
                meshRenderer.material.color = Color.white;
                
                Debug.Log($"[RoomViewer] Loaded OBJ with {vertices.Count} vertices");
            }
            catch (Exception e)
            {
                Debug.LogError($"[RoomViewer] Failed to load OBJ: {e.Message}");
                FlutterBridge.SendError($"Failed to load OBJ: {e.Message}");
            }
            
            yield return null;
        }
        
        private int ParseFaceIndex(string faceVertex)
        {
            // Handle formats: v, v/vt, v/vt/vn, v//vn
            var parts = faceVertex.Split('/');
            return int.Parse(parts[0]);
        }
        
        private void CenterCameraOnRoom()
        {
            if (loadedRoom == null) return;
            
            // Calculate bounds of all renderers
            var renderers = loadedRoom.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0) return;
            
            var bounds = renderers[0].bounds;
            foreach (var renderer in renderers)
            {
                bounds.Encapsulate(renderer.bounds);
            }
            
            // Set camera target to center of bounds
            cameraTarget.position = bounds.center;
            
            // Set zoom to fit the room
            float size = Mathf.Max(bounds.size.x, bounds.size.y, bounds.size.z);
            currentZoom = size * 1.5f;
            currentZoom = Mathf.Clamp(currentZoom, minZoom, maxZoom);
            
            UpdateCameraPosition();
        }
        
        private void HandleInput()
        {
            // Handle touch input
            if (Input.touchCount > 0)
            {
                HandleTouchInput();
            }
            // Handle mouse input (for editor testing)
            else if (Application.isEditor)
            {
                HandleMouseInput();
            }
            
            // Handle tap/click for selection
            if (Input.GetMouseButtonDown(0) && !isDragging)
            {
                TrySelectPart(Input.mousePosition);
            }
        }
        
        private void HandleTouchInput()
        {
            if (Input.touchCount == 1)
            {
                // Single finger - rotate
                Touch touch = Input.GetTouch(0);
                
                if (touch.phase == TouchPhase.Began)
                {
                    lastTouchPosition = touch.position;
                    isDragging = false;
                }
                else if (touch.phase == TouchPhase.Moved)
                {
                    Vector2 delta = touch.position - lastTouchPosition;
                    
                    if (delta.magnitude > 5f)
                    {
                        isDragging = true;
                        currentRotation.x += delta.y * rotationSpeed * 0.1f;
                        currentRotation.y += delta.x * rotationSpeed * 0.1f;
                        currentRotation.x = Mathf.Clamp(currentRotation.x, -80f, 80f);
                        UpdateCameraPosition();
                    }
                    
                    lastTouchPosition = touch.position;
                }
                else if (touch.phase == TouchPhase.Ended)
                {
                    if (!isDragging)
                    {
                        TrySelectPart(touch.position);
                    }
                    isDragging = false;
                }
            }
            else if (Input.touchCount == 2)
            {
                // Two fingers - pinch zoom and pan
                Touch touch0 = Input.GetTouch(0);
                Touch touch1 = Input.GetTouch(1);
                
                float currentPinchDistance = Vector2.Distance(touch0.position, touch1.position);
                
                if (touch0.phase == TouchPhase.Began || touch1.phase == TouchPhase.Began)
                {
                    lastPinchDistance = currentPinchDistance;
                }
                else if (touch0.phase == TouchPhase.Moved || touch1.phase == TouchPhase.Moved)
                {
                    // Zoom
                    float pinchDelta = currentPinchDistance - lastPinchDistance;
                    currentZoom -= pinchDelta * zoomSpeed * 0.01f;
                    currentZoom = Mathf.Clamp(currentZoom, minZoom, maxZoom);
                    
                    // Pan
                    Vector2 panDelta = (touch0.deltaPosition + touch1.deltaPosition) * 0.5f;
                    Vector3 right = viewCamera.transform.right;
                    Vector3 up = viewCamera.transform.up;
                    cameraTarget.position -= (right * panDelta.x + up * panDelta.y) * panSpeed * 0.01f;
                    
                    UpdateCameraPosition();
                    lastPinchDistance = currentPinchDistance;
                }
            }
        }
        
        private void HandleMouseInput()
        {
            // Right mouse button - rotate
            if (Input.GetMouseButton(1))
            {
                float mouseX = Input.GetAxis("Mouse X");
                float mouseY = Input.GetAxis("Mouse Y");
                
                currentRotation.y += mouseX * rotationSpeed;
                currentRotation.x -= mouseY * rotationSpeed;
                currentRotation.x = Mathf.Clamp(currentRotation.x, -80f, 80f);
                
                UpdateCameraPosition();
            }
            
            // Scroll wheel - zoom
            float scroll = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(scroll) > 0.01f)
            {
                currentZoom -= scroll * zoomSpeed * 5f;
                currentZoom = Mathf.Clamp(currentZoom, minZoom, maxZoom);
                UpdateCameraPosition();
            }
            
            // Middle mouse button - pan
            if (Input.GetMouseButton(2))
            {
                float mouseX = Input.GetAxis("Mouse X");
                float mouseY = Input.GetAxis("Mouse Y");
                
                Vector3 right = viewCamera.transform.right;
                Vector3 up = viewCamera.transform.up;
                cameraTarget.position -= (right * mouseX + up * mouseY) * panSpeed;
                
                UpdateCameraPosition();
            }
        }
        
        private void UpdateCameraPosition()
        {
            if (viewCamera == null || cameraTarget == null) return;
            
            // Calculate camera position using spherical coordinates
            float x = currentZoom * Mathf.Sin(currentRotation.y * Mathf.Deg2Rad) * Mathf.Cos(currentRotation.x * Mathf.Deg2Rad);
            float y = currentZoom * Mathf.Sin(currentRotation.x * Mathf.Deg2Rad);
            float z = currentZoom * Mathf.Cos(currentRotation.y * Mathf.Deg2Rad) * Mathf.Cos(currentRotation.x * Mathf.Deg2Rad);
            
            viewCamera.transform.position = cameraTarget.position + new Vector3(x, y, z);
            viewCamera.transform.LookAt(cameraTarget.position);
        }
        
        private void TrySelectPart(Vector2 screenPosition)
        {
            if (viewCamera == null) return;
            
            Ray ray = viewCamera.ScreenPointToRay(screenPosition);
            RaycastHit hit;
            
            if (Physics.Raycast(ray, out hit))
            {
                SelectPart(hit.collider.gameObject);
            }
            else
            {
                DeselectPart();
            }
        }
        
        /// <summary>
        /// Select a part by name (from Flutter)
        /// </summary>
        public void SelectPartByName(string partName)
        {
            if (loadedRoom == null) return;
            
            var transforms = loadedRoom.GetComponentsInChildren<Transform>();
            foreach (var t in transforms)
            {
                if (t.name.ToLower().Contains(partName.ToLower()))
                {
                    SelectPart(t.gameObject);
                    return;
                }
            }
            
            Debug.LogWarning($"[RoomViewer] Part not found: {partName}");
        }
        
        private void SelectPart(GameObject part)
        {
            // Deselect previous
            DeselectPart();
            
            selectedPart = part;
            
            // Store original material and apply highlight
            var renderer = part.GetComponent<Renderer>();
            if (renderer != null)
            {
                originalMaterial = renderer.material;
                
                if (selectionHighlightMaterial != null)
                {
                    // Create a copy with highlight
                    var highlightMat = new Material(originalMaterial);
                    highlightMat.SetColor("_EmissionColor", highlightColor);
                    highlightMat.EnableKeyword("_EMISSION");
                    renderer.material = highlightMat;
                }
            }
            
            FlutterBridge.SendPartSelected(part.name);
            Debug.Log($"[RoomViewer] Selected: {part.name}");
        }
        
        private void DeselectPart()
        {
            if (selectedPart != null)
            {
                // Restore original material
                var renderer = selectedPart.GetComponent<Renderer>();
                if (renderer != null && originalMaterial != null)
                {
                    renderer.material = originalMaterial;
                }
                
                selectedPart = null;
                originalMaterial = null;
            }
        }
        
        /// <summary>
        /// Get the currently selected part
        /// </summary>
        public GameObject GetSelectedPart()
        {
            return selectedPart;
        }
        
        /// <summary>
        /// Get the loaded room
        /// </summary>
        public GameObject GetLoadedRoom()
        {
            return loadedRoom;
        }
    }
}
