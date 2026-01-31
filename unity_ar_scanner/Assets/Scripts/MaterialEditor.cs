using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine.Networking;

namespace ReimagineAI
{
    /// <summary>
    /// Handles material editing for the scanned room
    /// </summary>
    public class MaterialEditor : MonoBehaviour
    {
        [Header("Default Materials")]
        [SerializeField] private Material defaultWallMaterial;
        [SerializeField] private Material defaultFloorMaterial;
        [SerializeField] private Material defaultCeilingMaterial;
        
        [Header("Settings")]
        [SerializeField] private bool allowUndoRedo = true;
        [SerializeField] private int maxUndoSteps = 20;
        
        private GameObject targetRoom;
        private Dictionary<Renderer, Material> originalMaterials = new Dictionary<Renderer, Material>();
        private Stack<MaterialEdit> undoStack = new Stack<MaterialEdit>();
        private Stack<MaterialEdit> redoStack = new Stack<MaterialEdit>();
        
        private void OnEnable()
        {
            FlutterBridge.OnEditMaterial += ApplyEdit;
        }
        
        private void OnDisable()
        {
            FlutterBridge.OnEditMaterial -= ApplyEdit;
        }
        
        /// <summary>
        /// Set the target room for editing
        /// </summary>
        public void SetTargetRoom(GameObject room)
        {
            targetRoom = room;
            
            // Store original materials
            originalMaterials.Clear();
            var renderers = room.GetComponentsInChildren<Renderer>();
            foreach (var renderer in renderers)
            {
                originalMaterials[renderer] = renderer.material;
            }
            
            Debug.Log($"[MaterialEditor] Target room set with {renderers.Length} renderers");
        }
        
        /// <summary>
        /// Apply an edit from JSON string
        /// </summary>
        public void ApplyEdit(string editJson)
        {
            try
            {
                var edit = JsonUtility.FromJson<MaterialEditData>(editJson);
                ApplyMaterialEdit(edit);
            }
            catch (Exception e)
            {
                Debug.LogError($"[MaterialEditor] Failed to parse edit: {e.Message}");
                FlutterBridge.SendError($"Failed to parse edit: {e.Message}");
            }
        }
        
        /// <summary>
        /// Apply a material edit
        /// </summary>
        public void ApplyMaterialEdit(MaterialEditData edit)
        {
            if (targetRoom == null)
            {
                FlutterBridge.SendError("No room loaded");
                return;
            }
            
            Debug.Log($"[MaterialEditor] Applying edit - Target: {edit.target}, Property: {edit.property}, Value: {edit.value}");
            
            // Find matching renderers
            var matchingRenderers = FindMatchingRenderers(edit.target);
            
            if (matchingRenderers.Count == 0)
            {
                Debug.LogWarning($"[MaterialEditor] No matching parts found for: {edit.target}");
                FlutterBridge.SendError($"No matching parts found for: {edit.target}");
                return;
            }
            
            // Store for undo
            var previousEdit = new MaterialEdit
            {
                editData = edit,
                affectedRenderers = matchingRenderers,
                previousMaterials = new Dictionary<Renderer, Material>()
            };
            
            foreach (var renderer in matchingRenderers)
            {
                previousEdit.previousMaterials[renderer] = renderer.material;
            }
            
            // Apply the edit based on property type
            switch (edit.property.ToLower())
            {
                case "color":
                    ApplyColorEdit(matchingRenderers, edit.value);
                    break;
                    
                case "texture":
                    StartCoroutine(ApplyTextureEdit(matchingRenderers, edit.value));
                    break;
                    
                case "material":
                    ApplyMaterialPreset(matchingRenderers, edit.value);
                    break;
                    
                default:
                    Debug.LogWarning($"[MaterialEditor] Unknown property: {edit.property}");
                    FlutterBridge.SendError($"Unknown property: {edit.property}");
                    return;
            }
            
            // Add to undo stack
            if (allowUndoRedo)
            {
                undoStack.Push(previousEdit);
                if (undoStack.Count > maxUndoSteps)
                {
                    // Remove oldest
                }
                redoStack.Clear();
            }
            
            FlutterBridge.SendEditApplied(edit.target);
            Debug.Log($"[MaterialEditor] Edit applied to {matchingRenderers.Count} renderers");
        }
        
        private List<Renderer> FindMatchingRenderers(string target)
        {
            var matching = new List<Renderer>();
            
            if (targetRoom == null) return matching;
            
            var renderers = targetRoom.GetComponentsInChildren<Renderer>();
            string targetLower = target.ToLower();
            
            foreach (var renderer in renderers)
            {
                string name = renderer.gameObject.name.ToLower();
                
                // Match by common naming conventions
                bool isMatch = false;
                
                if (targetLower == "wall" || targetLower == "walls")
                {
                    isMatch = name.Contains("wall") || name.Contains("vertical");
                }
                else if (targetLower == "floor")
                {
                    isMatch = name.Contains("floor") || name.Contains("ground");
                }
                else if (targetLower == "ceiling")
                {
                    isMatch = name.Contains("ceiling") || name.Contains("roof");
                }
                else if (targetLower == "furniture")
                {
                    isMatch = name.Contains("furniture") || name.Contains("chair") || 
                             name.Contains("table") || name.Contains("sofa") || name.Contains("bed");
                }
                else if (targetLower == "door" || targetLower == "doors")
                {
                    isMatch = name.Contains("door");
                }
                else if (targetLower == "window" || targetLower == "windows")
                {
                    isMatch = name.Contains("window");
                }
                else
                {
                    // Generic match
                    isMatch = name.Contains(targetLower);
                }
                
                if (isMatch)
                {
                    matching.Add(renderer);
                }
            }
            
            // If no specific match, try matching all (for "all" or "everything")
            if (matching.Count == 0 && (targetLower == "all" || targetLower == "everything" || targetLower == "room"))
            {
                matching.AddRange(renderers);
            }
            
            return matching;
        }
        
        private void ApplyColorEdit(List<Renderer> renderers, string colorValue)
        {
            Color color;
            
            // Try parsing as hex color
            if (colorValue.StartsWith("#"))
            {
                if (!ColorUtility.TryParseHtmlString(colorValue, out color))
                {
                    Debug.LogError($"[MaterialEditor] Invalid hex color: {colorValue}");
                    return;
                }
            }
            // Try parsing as named color
            else if (!TryParseNamedColor(colorValue, out color))
            {
                Debug.LogError($"[MaterialEditor] Unknown color: {colorValue}");
                return;
            }
            
            foreach (var renderer in renderers)
            {
                // Create a new material instance to avoid sharing
                var material = new Material(renderer.material);
                material.color = color;
                
                // Also set emission for better visibility
                if (material.HasProperty("_EmissionColor"))
                {
                    material.SetColor("_EmissionColor", color * 0.1f);
                }
                
                renderer.material = material;
            }
            
            Debug.Log($"[MaterialEditor] Applied color {colorValue} to {renderers.Count} renderers");
        }
        
        private IEnumerator ApplyTextureEdit(List<Renderer> renderers, string textureValue)
        {
            // Check if it's a URL or base64
            if (textureValue.StartsWith("http"))
            {
                // Load from URL
                using (var request = UnityWebRequestTexture.GetTexture(textureValue))
                {
                    yield return request.SendWebRequest();
                    
                    if (request.result == UnityWebRequest.Result.Success)
                    {
                        var texture = DownloadHandlerTexture.GetContent(request);
                        ApplyTexture(renderers, texture);
                    }
                    else
                    {
                        Debug.LogError($"[MaterialEditor] Failed to load texture: {request.error}");
                        FlutterBridge.SendError($"Failed to load texture: {request.error}");
                    }
                }
            }
            else if (textureValue.StartsWith("data:"))
            {
                // Load from base64
                try
                {
                    string base64 = textureValue.Substring(textureValue.IndexOf(",") + 1);
                    byte[] imageData = Convert.FromBase64String(base64);
                    
                    var texture = new Texture2D(2, 2);
                    texture.LoadImage(imageData);
                    
                    ApplyTexture(renderers, texture);
                }
                catch (Exception e)
                {
                    Debug.LogError($"[MaterialEditor] Failed to parse base64 texture: {e.Message}");
                    FlutterBridge.SendError($"Failed to parse texture: {e.Message}");
                }
            }
            else
            {
                // Treat as material/texture description - would need AI to generate
                Debug.Log($"[MaterialEditor] Texture description: {textureValue} - would need texture generation");
                FlutterBridge.SendMessageToFlutter("needsTextureGeneration", textureValue);
            }
        }
        
        private void ApplyTexture(List<Renderer> renderers, Texture2D texture)
        {
            foreach (var renderer in renderers)
            {
                var material = new Material(renderer.material);
                material.mainTexture = texture;
                renderer.material = material;
            }
            
            Debug.Log($"[MaterialEditor] Applied texture to {renderers.Count} renderers");
        }
        
        private void ApplyMaterialPreset(List<Renderer> renderers, string presetName)
        {
            Material preset = null;
            string presetLower = presetName.ToLower();
            
            // Check for built-in presets
            if (presetLower.Contains("wood") || presetLower.Contains("hardwood"))
            {
                // Create wood-like material
                preset = CreateWoodMaterial();
            }
            else if (presetLower.Contains("marble") || presetLower.Contains("stone"))
            {
                preset = CreateStoneMaterial();
            }
            else if (presetLower.Contains("metal") || presetLower.Contains("steel"))
            {
                preset = CreateMetalMaterial();
            }
            else if (presetLower.Contains("glass"))
            {
                preset = CreateGlassMaterial();
            }
            else
            {
                // Try loading from resources
                preset = Resources.Load<Material>($"Materials/{presetName}");
            }
            
            if (preset != null)
            {
                foreach (var renderer in renderers)
                {
                    renderer.material = new Material(preset);
                }
                Debug.Log($"[MaterialEditor] Applied preset '{presetName}' to {renderers.Count} renderers");
            }
            else
            {
                Debug.LogWarning($"[MaterialEditor] Preset not found: {presetName}");
                FlutterBridge.SendError($"Material preset not found: {presetName}");
            }
        }
        
        private bool TryParseNamedColor(string name, out Color color)
        {
            color = Color.white;
            string nameLower = name.ToLower().Trim();
            
            switch (nameLower)
            {
                case "white": color = Color.white; return true;
                case "black": color = Color.black; return true;
                case "red": color = Color.red; return true;
                case "green": color = Color.green; return true;
                case "blue": color = Color.blue; return true;
                case "yellow": color = Color.yellow; return true;
                case "cyan": color = Color.cyan; return true;
                case "magenta": color = Color.magenta; return true;
                case "gray": case "grey": color = Color.gray; return true;
                case "navy": case "navy blue": color = new Color(0f, 0f, 0.5f); return true;
                case "beige": color = new Color(0.96f, 0.96f, 0.86f); return true;
                case "cream": color = new Color(1f, 0.99f, 0.82f); return true;
                case "brown": color = new Color(0.6f, 0.3f, 0f); return true;
                case "tan": color = new Color(0.82f, 0.71f, 0.55f); return true;
                case "olive": color = new Color(0.5f, 0.5f, 0f); return true;
                case "teal": color = new Color(0f, 0.5f, 0.5f); return true;
                case "coral": color = new Color(1f, 0.5f, 0.31f); return true;
                case "salmon": color = new Color(0.98f, 0.5f, 0.45f); return true;
                case "lavender": color = new Color(0.9f, 0.9f, 0.98f); return true;
                case "mint": color = new Color(0.6f, 1f, 0.6f); return true;
                case "peach": color = new Color(1f, 0.9f, 0.71f); return true;
                default: return false;
            }
        }
        
        private Material CreateWoodMaterial()
        {
            var material = new Material(Shader.Find("Standard"));
            material.color = new Color(0.55f, 0.35f, 0.17f);
            material.SetFloat("_Metallic", 0f);
            material.SetFloat("_Glossiness", 0.3f);
            return material;
        }
        
        private Material CreateStoneMaterial()
        {
            var material = new Material(Shader.Find("Standard"));
            material.color = new Color(0.7f, 0.7f, 0.7f);
            material.SetFloat("_Metallic", 0f);
            material.SetFloat("_Glossiness", 0.1f);
            return material;
        }
        
        private Material CreateMetalMaterial()
        {
            var material = new Material(Shader.Find("Standard"));
            material.color = new Color(0.8f, 0.8f, 0.8f);
            material.SetFloat("_Metallic", 1f);
            material.SetFloat("_Glossiness", 0.8f);
            return material;
        }
        
        private Material CreateGlassMaterial()
        {
            var material = new Material(Shader.Find("Standard"));
            material.color = new Color(0.8f, 0.9f, 1f, 0.3f);
            material.SetFloat("_Mode", 3); // Transparent
            material.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            material.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            material.SetInt("_ZWrite", 0);
            material.DisableKeyword("_ALPHATEST_ON");
            material.EnableKeyword("_ALPHABLEND_ON");
            material.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            material.renderQueue = 3000;
            return material;
        }
        
        /// <summary>
        /// Undo the last edit
        /// </summary>
        public void Undo()
        {
            if (undoStack.Count == 0) return;
            
            var edit = undoStack.Pop();
            
            // Store current state for redo
            var redoEdit = new MaterialEdit
            {
                editData = edit.editData,
                affectedRenderers = edit.affectedRenderers,
                previousMaterials = new Dictionary<Renderer, Material>()
            };
            
            // Restore previous materials
            foreach (var kvp in edit.previousMaterials)
            {
                redoEdit.previousMaterials[kvp.Key] = kvp.Key.material;
                kvp.Key.material = kvp.Value;
            }
            
            redoStack.Push(redoEdit);
            
            FlutterBridge.SendMessageToFlutter("undoApplied", "");
        }
        
        /// <summary>
        /// Redo the last undone edit
        /// </summary>
        public void Redo()
        {
            if (redoStack.Count == 0) return;
            
            var edit = redoStack.Pop();
            
            // Store current state for undo
            var undoEdit = new MaterialEdit
            {
                editData = edit.editData,
                affectedRenderers = edit.affectedRenderers,
                previousMaterials = new Dictionary<Renderer, Material>()
            };
            
            // Restore redo materials
            foreach (var kvp in edit.previousMaterials)
            {
                undoEdit.previousMaterials[kvp.Key] = kvp.Key.material;
                kvp.Key.material = kvp.Value;
            }
            
            undoStack.Push(undoEdit);
            
            FlutterBridge.SendMessageToFlutter("redoApplied", "");
        }
        
        /// <summary>
        /// Reset all materials to original
        /// </summary>
        public void ResetToOriginal()
        {
            foreach (var kvp in originalMaterials)
            {
                if (kvp.Key != null)
                {
                    kvp.Key.material = kvp.Value;
                }
            }
            
            undoStack.Clear();
            redoStack.Clear();
            
            FlutterBridge.SendMessageToFlutter("materialsReset", "");
        }
        
        private class MaterialEdit
        {
            public MaterialEditData editData;
            public List<Renderer> affectedRenderers;
            public Dictionary<Renderer, Material> previousMaterials;
        }
    }
    
    [Serializable]
    public class MaterialEditData
    {
        public string target;   // "wall", "floor", "ceiling", etc.
        public string property; // "color", "texture", "material"
        public string value;    // "#FF5733", URL, or preset name
    }
}
