using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;
using System.Collections.Generic;
using System.IO;

namespace ReimagineAI
{
    /// <summary>
    /// Controls AR room scanning using AR Foundation's mesh manager
    /// </summary>
    public class RoomScannerController : MonoBehaviour
    {
        [Header("AR Components")]
        [SerializeField] private ARSession arSession;
        [SerializeField] private ARMeshManager meshManager;
        [SerializeField] private ARPlaneManager planeManager;
        
        [Header("Scanning Settings")]
        [SerializeField] private float meshDensity = 0.5f;
        [SerializeField] private bool generateNormals = true;
        [SerializeField] private bool showMeshVisualization = true;
        
        [Header("Visual Feedback")]
        [SerializeField] private Material scanningMaterial;
        [SerializeField] private Material completedMaterial;
        
        [Header("Export Settings")]
        [SerializeField] private MeshExporter meshExporter;
        
        private bool isScanning = false;
        private float scanProgress = 0f;
        private List<MeshFilter> capturedMeshes = new List<MeshFilter>();
        private int totalMeshesGenerated = 0;
        
        private void OnEnable()
        {
            // Subscribe to Flutter bridge events
            FlutterBridge.OnStartScan += StartScanning;
            FlutterBridge.OnStopScan += StopScanning;
            FlutterBridge.OnExportRoom += ExportRoom;
            
            // Subscribe to mesh events
            if (meshManager != null)
            {
                meshManager.meshesChanged += OnMeshesChanged;
            }
        }
        
        private void OnDisable()
        {
            // Unsubscribe from events
            FlutterBridge.OnStartScan -= StartScanning;
            FlutterBridge.OnStopScan -= StopScanning;
            FlutterBridge.OnExportRoom -= ExportRoom;
            
            if (meshManager != null)
            {
                meshManager.meshesChanged -= OnMeshesChanged;
            }
        }
        
        private void Start()
        {
            // Initialize AR components
            if (meshManager != null)
            {
                meshManager.enabled = false; // Start disabled
            }
            
            if (planeManager != null)
            {
                planeManager.enabled = true; // Planes help with initial tracking
            }
            
            Debug.Log("[RoomScanner] Initialized and ready");
        }
        
        private void Update()
        {
            if (isScanning)
            {
                UpdateScanProgress();
            }
        }
        
        /// <summary>
        /// Start the room scanning process
        /// </summary>
        public void StartScanning()
        {
            if (isScanning)
            {
                Debug.LogWarning("[RoomScanner] Already scanning");
                return;
            }
            
            Debug.Log("[RoomScanner] Starting room scan...");
            
            isScanning = true;
            scanProgress = 0f;
            capturedMeshes.Clear();
            totalMeshesGenerated = 0;
            
            // Enable mesh manager
            if (meshManager != null)
            {
                meshManager.enabled = true;
            }
            
            // Optionally disable plane visualization during scanning
            if (planeManager != null)
            {
                SetPlanesVisible(false);
            }
            
            FlutterBridge.SendScanProgress(0f);
        }
        
        /// <summary>
        /// Stop the scanning process
        /// </summary>
        public void StopScanning()
        {
            if (!isScanning)
            {
                Debug.LogWarning("[RoomScanner] Not currently scanning");
                return;
            }
            
            Debug.Log("[RoomScanner] Stopping scan...");
            
            isScanning = false;
            
            // Keep mesh manager enabled but stop updating
            // This preserves the generated meshes
            
            FlutterBridge.SendScanProgress(1f);
        }
        
        /// <summary>
        /// Export the scanned room to glTF format
        /// </summary>
        public void ExportRoom()
        {
            Debug.Log("[RoomScanner] Exporting room...");
            
            // Collect all meshes from the mesh manager
            var meshFilters = CollectAllMeshes();
            
            if (meshFilters.Count == 0)
            {
                Debug.LogError("[RoomScanner] No meshes to export");
                FlutterBridge.SendError("No meshes captured. Please scan the room first.");
                return;
            }
            
            // Combine meshes into a single mesh
            Mesh combinedMesh = CombineMeshes(meshFilters);
            
            if (combinedMesh == null)
            {
                FlutterBridge.SendError("Failed to combine meshes");
                return;
            }
            
            // Export to glTF/GLB
            string exportPath = GetExportPath();
            
            if (meshExporter != null)
            {
                bool success = meshExporter.ExportMeshToGLB(combinedMesh, exportPath);
                
                if (success)
                {
                    Debug.Log($"[RoomScanner] Room exported to: {exportPath}");
                    FlutterBridge.SendRoomExported(exportPath);
                }
                else
                {
                    FlutterBridge.SendError("Failed to export room");
                }
            }
            else
            {
                // Fallback: Save as OBJ if no exporter configured
                string objPath = exportPath.Replace(".glb", ".obj");
                SaveMeshAsOBJ(combinedMesh, objPath);
                FlutterBridge.SendRoomExported(objPath);
            }
        }
        
        private void OnMeshesChanged(ARMeshesChangedEventArgs args)
        {
            // Handle added meshes
            foreach (var mesh in args.added)
            {
                var meshFilter = mesh.GetComponent<MeshFilter>();
                if (meshFilter != null && !capturedMeshes.Contains(meshFilter))
                {
                    capturedMeshes.Add(meshFilter);
                    totalMeshesGenerated++;
                    
                    // Apply scanning material
                    var renderer = mesh.GetComponent<MeshRenderer>();
                    if (renderer != null && scanningMaterial != null)
                    {
                        renderer.material = scanningMaterial;
                        renderer.enabled = showMeshVisualization;
                    }
                }
            }
            
            // Handle updated meshes
            foreach (var mesh in args.updated)
            {
                // Meshes are updated in place, no action needed
            }
            
            // Handle removed meshes
            foreach (var mesh in args.removed)
            {
                var meshFilter = mesh.GetComponent<MeshFilter>();
                if (meshFilter != null)
                {
                    capturedMeshes.Remove(meshFilter);
                }
            }
        }
        
        private void UpdateScanProgress()
        {
            // Calculate progress based on mesh coverage
            // This is a simplified progress calculation
            float targetMeshCount = 50f; // Expected number of mesh segments for a room
            scanProgress = Mathf.Clamp01(totalMeshesGenerated / targetMeshCount);
            
            // Send progress update to Flutter (throttled)
            if (Time.frameCount % 30 == 0) // Update every 30 frames
            {
                FlutterBridge.SendScanProgress(scanProgress);
            }
        }
        
        private List<MeshFilter> CollectAllMeshes()
        {
            var meshFilters = new List<MeshFilter>();
            
            if (meshManager != null)
            {
                // Get all mesh filters from the mesh manager's children
                var filters = meshManager.GetComponentsInChildren<MeshFilter>();
                foreach (var filter in filters)
                {
                    if (filter.sharedMesh != null && filter.sharedMesh.vertexCount > 0)
                    {
                        meshFilters.Add(filter);
                    }
                }
            }
            
            // Also include any manually captured meshes
            foreach (var filter in capturedMeshes)
            {
                if (filter != null && !meshFilters.Contains(filter))
                {
                    meshFilters.Add(filter);
                }
            }
            
            Debug.Log($"[RoomScanner] Collected {meshFilters.Count} meshes");
            return meshFilters;
        }
        
        private Mesh CombineMeshes(List<MeshFilter> meshFilters)
        {
            if (meshFilters.Count == 0) return null;
            
            // Prepare combine instances
            var combineInstances = new CombineInstance[meshFilters.Count];
            
            for (int i = 0; i < meshFilters.Count; i++)
            {
                combineInstances[i].mesh = meshFilters[i].sharedMesh;
                combineInstances[i].transform = meshFilters[i].transform.localToWorldMatrix;
            }
            
            // Create combined mesh
            var combinedMesh = new Mesh();
            combinedMesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32; // Support large meshes
            combinedMesh.CombineMeshes(combineInstances, true, true);
            
            if (generateNormals)
            {
                combinedMesh.RecalculateNormals();
            }
            
            combinedMesh.RecalculateBounds();
            
            Debug.Log($"[RoomScanner] Combined mesh: {combinedMesh.vertexCount} vertices, {combinedMesh.triangles.Length / 3} triangles");
            
            return combinedMesh;
        }
        
        private string GetExportPath()
        {
            string fileName = $"room_scan_{System.DateTime.Now:yyyyMMdd_HHmmss}.glb";
            return Path.Combine(Application.persistentDataPath, fileName);
        }
        
        private void SaveMeshAsOBJ(Mesh mesh, string path)
        {
            // Simple OBJ export as fallback
            using (var writer = new StreamWriter(path))
            {
                writer.WriteLine("# Room Scan Export");
                writer.WriteLine($"# Vertices: {mesh.vertexCount}");
                writer.WriteLine($"# Triangles: {mesh.triangles.Length / 3}");
                writer.WriteLine();
                
                // Write vertices
                foreach (var v in mesh.vertices)
                {
                    writer.WriteLine($"v {v.x} {v.y} {v.z}");
                }
                
                // Write normals
                foreach (var n in mesh.normals)
                {
                    writer.WriteLine($"vn {n.x} {n.y} {n.z}");
                }
                
                // Write UVs
                foreach (var uv in mesh.uv)
                {
                    writer.WriteLine($"vt {uv.x} {uv.y}");
                }
                
                // Write faces
                var triangles = mesh.triangles;
                for (int i = 0; i < triangles.Length; i += 3)
                {
                    // OBJ indices are 1-based
                    int v1 = triangles[i] + 1;
                    int v2 = triangles[i + 1] + 1;
                    int v3 = triangles[i + 2] + 1;
                    writer.WriteLine($"f {v1}/{v1}/{v1} {v2}/{v2}/{v2} {v3}/{v3}/{v3}");
                }
            }
            
            Debug.Log($"[RoomScanner] Saved OBJ to: {path}");
        }
        
        private void SetPlanesVisible(bool visible)
        {
            if (planeManager == null) return;
            
            foreach (var plane in planeManager.trackables)
            {
                plane.gameObject.SetActive(visible);
            }
        }
        
        /// <summary>
        /// Reset the scanner for a new scan
        /// </summary>
        public void ResetScanner()
        {
            StopScanning();
            
            // Destroy captured meshes
            if (meshManager != null)
            {
                // AR Foundation manages mesh lifecycle
            }
            
            capturedMeshes.Clear();
            totalMeshesGenerated = 0;
            scanProgress = 0f;
            
            Debug.Log("[RoomScanner] Scanner reset");
        }
    }
}
