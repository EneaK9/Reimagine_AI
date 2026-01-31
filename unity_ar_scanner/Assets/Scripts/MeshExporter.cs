using UnityEngine;
using System;
using System.IO;
using System.Collections.Generic;
using System.Text;

namespace ReimagineAI
{
    /// <summary>
    /// Exports Unity meshes to glTF/GLB format
    /// </summary>
    public class MeshExporter : MonoBehaviour
    {
        [Header("Export Settings")]
        [SerializeField] private bool embedTextures = true;
        [SerializeField] private bool useCompression = false;
        
        /// <summary>
        /// Export a mesh to GLB (binary glTF) format
        /// </summary>
        public bool ExportMeshToGLB(Mesh mesh, string outputPath)
        {
            try
            {
                Debug.Log($"[MeshExporter] Exporting mesh to: {outputPath}");
                
                // Create glTF structure
                var gltf = CreateGLTFFromMesh(mesh);
                
                // Write to file
                WriteGLBFile(gltf, outputPath);
                
                Debug.Log($"[MeshExporter] Export successful: {outputPath}");
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError($"[MeshExporter] Export failed: {e.Message}");
                return false;
            }
        }
        
        /// <summary>
        /// Export a GameObject with all its meshes to GLB
        /// </summary>
        public bool ExportGameObjectToGLB(GameObject gameObject, string outputPath)
        {
            try
            {
                var meshFilters = gameObject.GetComponentsInChildren<MeshFilter>();
                if (meshFilters.Length == 0)
                {
                    Debug.LogError("[MeshExporter] No meshes found in GameObject");
                    return false;
                }
                
                // Combine all meshes
                var combineInstances = new CombineInstance[meshFilters.Length];
                for (int i = 0; i < meshFilters.Length; i++)
                {
                    combineInstances[i].mesh = meshFilters[i].sharedMesh;
                    combineInstances[i].transform = meshFilters[i].transform.localToWorldMatrix;
                }
                
                var combinedMesh = new Mesh();
                combinedMesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
                combinedMesh.CombineMeshes(combineInstances, true, true);
                combinedMesh.RecalculateNormals();
                combinedMesh.RecalculateBounds();
                
                return ExportMeshToGLB(combinedMesh, outputPath);
            }
            catch (Exception e)
            {
                Debug.LogError($"[MeshExporter] Export failed: {e.Message}");
                return false;
            }
        }
        
        private GLTFData CreateGLTFFromMesh(Mesh mesh)
        {
            var gltf = new GLTFData();
            
            // Get mesh data
            var vertices = mesh.vertices;
            var normals = mesh.normals;
            var uvs = mesh.uv;
            var indices = mesh.triangles;
            
            // Calculate bounds
            var bounds = mesh.bounds;
            
            // Create binary buffer
            var bufferData = new List<byte>();
            
            // Write indices (as unsigned shorts or ints)
            int indicesOffset = 0;
            int indicesLength = 0;
            bool useShortIndices = vertices.Length <= 65535;
            
            if (useShortIndices)
            {
                foreach (var index in indices)
                {
                    bufferData.AddRange(BitConverter.GetBytes((ushort)index));
                }
                indicesLength = indices.Length * 2;
            }
            else
            {
                foreach (var index in indices)
                {
                    bufferData.AddRange(BitConverter.GetBytes((uint)index));
                }
                indicesLength = indices.Length * 4;
            }
            
            // Pad to 4-byte alignment
            while (bufferData.Count % 4 != 0)
            {
                bufferData.Add(0);
            }
            
            // Write vertices
            int verticesOffset = bufferData.Count;
            foreach (var v in vertices)
            {
                bufferData.AddRange(BitConverter.GetBytes(v.x));
                bufferData.AddRange(BitConverter.GetBytes(v.y));
                bufferData.AddRange(BitConverter.GetBytes(v.z));
            }
            int verticesLength = vertices.Length * 12;
            
            // Write normals
            int normalsOffset = bufferData.Count;
            int normalsLength = 0;
            if (normals != null && normals.Length > 0)
            {
                foreach (var n in normals)
                {
                    bufferData.AddRange(BitConverter.GetBytes(n.x));
                    bufferData.AddRange(BitConverter.GetBytes(n.y));
                    bufferData.AddRange(BitConverter.GetBytes(n.z));
                }
                normalsLength = normals.Length * 12;
            }
            
            // Write UVs
            int uvsOffset = bufferData.Count;
            int uvsLength = 0;
            if (uvs != null && uvs.Length > 0)
            {
                foreach (var uv in uvs)
                {
                    bufferData.AddRange(BitConverter.GetBytes(uv.x));
                    bufferData.AddRange(BitConverter.GetBytes(uv.y));
                }
                uvsLength = uvs.Length * 8;
            }
            
            gltf.BinaryData = bufferData.ToArray();
            
            // Build JSON structure
            var json = new StringBuilder();
            json.Append("{");
            
            // Asset info
            json.Append("\"asset\":{\"version\":\"2.0\",\"generator\":\"ReimagineAI Unity Exporter\"},");
            
            // Scene
            json.Append("\"scene\":0,");
            json.Append("\"scenes\":[{\"nodes\":[0]}],");
            
            // Nodes
            json.Append("\"nodes\":[{\"mesh\":0,\"name\":\"RoomScan\"}],");
            
            // Meshes
            json.Append("\"meshes\":[{\"primitives\":[{");
            json.Append("\"attributes\":{");
            json.Append("\"POSITION\":1");
            if (normalsLength > 0) json.Append(",\"NORMAL\":2");
            if (uvsLength > 0) json.Append(",\"TEXCOORD_0\":3");
            json.Append("},");
            json.Append("\"indices\":0,");
            json.Append("\"material\":0");
            json.Append("}],\"name\":\"RoomMesh\"}],");
            
            // Materials
            json.Append("\"materials\":[{");
            json.Append("\"name\":\"RoomMaterial\",");
            json.Append("\"pbrMetallicRoughness\":{");
            json.Append("\"baseColorFactor\":[0.8,0.8,0.8,1.0],");
            json.Append("\"metallicFactor\":0.0,");
            json.Append("\"roughnessFactor\":0.8");
            json.Append("}}],");
            
            // Accessors
            json.Append("\"accessors\":[");
            
            // Indices accessor
            json.Append("{");
            json.Append("\"bufferView\":0,");
            json.Append($"\"componentType\":{(useShortIndices ? 5123 : 5125)},"); // UNSIGNED_SHORT or UNSIGNED_INT
            json.Append($"\"count\":{indices.Length},");
            json.Append("\"type\":\"SCALAR\"");
            json.Append("},");
            
            // Position accessor
            json.Append("{");
            json.Append("\"bufferView\":1,");
            json.Append("\"componentType\":5126,"); // FLOAT
            json.Append($"\"count\":{vertices.Length},");
            json.Append("\"type\":\"VEC3\",");
            json.AppendFormat("\"min\":[{0},{1},{2}],", bounds.min.x, bounds.min.y, bounds.min.z);
            json.AppendFormat("\"max\":[{0},{1},{2}]", bounds.max.x, bounds.max.y, bounds.max.z);
            json.Append("}");
            
            // Normal accessor
            if (normalsLength > 0)
            {
                json.Append(",{");
                json.Append("\"bufferView\":2,");
                json.Append("\"componentType\":5126,");
                json.Append($"\"count\":{normals.Length},");
                json.Append("\"type\":\"VEC3\"");
                json.Append("}");
            }
            
            // UV accessor
            if (uvsLength > 0)
            {
                json.Append(",{");
                json.Append($"\"bufferView\":{(normalsLength > 0 ? 3 : 2)},");
                json.Append("\"componentType\":5126,");
                json.Append($"\"count\":{uvs.Length},");
                json.Append("\"type\":\"VEC2\"");
                json.Append("}");
            }
            
            json.Append("],");
            
            // Buffer views
            json.Append("\"bufferViews\":[");
            
            // Indices buffer view
            json.Append("{");
            json.Append("\"buffer\":0,");
            json.Append($"\"byteOffset\":{indicesOffset},");
            json.Append($"\"byteLength\":{indicesLength},");
            json.Append("\"target\":34963"); // ELEMENT_ARRAY_BUFFER
            json.Append("},");
            
            // Vertices buffer view
            json.Append("{");
            json.Append("\"buffer\":0,");
            json.Append($"\"byteOffset\":{verticesOffset},");
            json.Append($"\"byteLength\":{verticesLength},");
            json.Append("\"target\":34962"); // ARRAY_BUFFER
            json.Append("}");
            
            // Normals buffer view
            if (normalsLength > 0)
            {
                json.Append(",{");
                json.Append("\"buffer\":0,");
                json.Append($"\"byteOffset\":{normalsOffset},");
                json.Append($"\"byteLength\":{normalsLength},");
                json.Append("\"target\":34962");
                json.Append("}");
            }
            
            // UVs buffer view
            if (uvsLength > 0)
            {
                json.Append(",{");
                json.Append("\"buffer\":0,");
                json.Append($"\"byteOffset\":{uvsOffset},");
                json.Append($"\"byteLength\":{uvsLength},");
                json.Append("\"target\":34962");
                json.Append("}");
            }
            
            json.Append("],");
            
            // Buffers
            json.Append("\"buffers\":[{");
            json.Append($"\"byteLength\":{bufferData.Count}");
            json.Append("}]");
            
            json.Append("}");
            
            gltf.JsonData = json.ToString();
            
            return gltf;
        }
        
        private void WriteGLBFile(GLTFData gltf, string outputPath)
        {
            using (var stream = new FileStream(outputPath, FileMode.Create))
            using (var writer = new BinaryWriter(stream))
            {
                var jsonBytes = Encoding.UTF8.GetBytes(gltf.JsonData);
                
                // Pad JSON to 4-byte alignment
                int jsonPadding = (4 - (jsonBytes.Length % 4)) % 4;
                int paddedJsonLength = jsonBytes.Length + jsonPadding;
                
                // Calculate total file length
                int headerLength = 12;
                int jsonChunkHeaderLength = 8;
                int binaryChunkHeaderLength = 8;
                int totalLength = headerLength + jsonChunkHeaderLength + paddedJsonLength + 
                                  binaryChunkHeaderLength + gltf.BinaryData.Length;
                
                // GLB Header
                writer.Write(0x46546C67); // "glTF" magic
                writer.Write(2); // Version 2
                writer.Write(totalLength);
                
                // JSON Chunk
                writer.Write(paddedJsonLength);
                writer.Write(0x4E4F534A); // "JSON"
                writer.Write(jsonBytes);
                for (int i = 0; i < jsonPadding; i++)
                {
                    writer.Write((byte)0x20); // Space padding
                }
                
                // Binary Chunk
                writer.Write(gltf.BinaryData.Length);
                writer.Write(0x004E4942); // "BIN\0"
                writer.Write(gltf.BinaryData);
            }
        }
        
        private class GLTFData
        {
            public string JsonData;
            public byte[] BinaryData;
        }
    }
}
