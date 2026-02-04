"""
ReimagineAI - Depth Estimation and 3D Mesh Generation Service
Uses MiDaS for monocular depth estimation and Open3D for mesh generation
"""
import os
import uuid
import base64
from io import BytesIO
from typing import Optional, Tuple
import numpy as np
from PIL import Image

# These imports are conditionally loaded to avoid startup errors
# if dependencies aren't installed yet
_torch_available = False
_open3d_available = False

try:
    import torch
    import torch.nn.functional as F
    _torch_available = True
except ImportError:
    print("Warning: PyTorch not available. Depth estimation will not work.")

try:
    import open3d as o3d
    _open3d_available = True
except ImportError:
    print("Warning: Open3D not available. Mesh generation will not work.")


class DepthService:
    """
    Service for generating depth maps and 3D meshes from room photos.
    
    Uses:
    - MiDaS (DPT_Hybrid) for monocular depth estimation
    - Open3D for point cloud and mesh generation
    """
    
    def __init__(self):
        self.model = None
        self.transform = None
        self.device = None
        self._initialized = False
        
        # Storage paths
        self.data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        self.meshes_dir = os.path.join(self.data_dir, 'meshes')
        os.makedirs(self.meshes_dir, exist_ok=True)
    
    def _ensure_initialized(self):
        """Lazy initialization of MiDaS model to avoid slow startup."""
        if self._initialized:
            return
        
        if not _torch_available:
            raise RuntimeError("PyTorch is not installed. Run: pip install torch torchvision timm")
        
        print("Loading MiDaS depth estimation model...")
        
        # Use CPU by default, GPU if available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # Load MiDaS model - DPT_Hybrid is a good balance of speed and quality
        # Other options: "DPT_Large" (better quality), "MiDaS_small" (faster)
        self.model = torch.hub.load("intel-isl/MiDaS", "DPT_Hybrid")
        self.model.to(self.device)
        self.model.eval()
        
        # Load transforms
        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
        self.transform = midas_transforms.dpt_transform
        
        self._initialized = True
        print("MiDaS model loaded successfully!")
    
    def _decode_base64_image(self, image_base64: str) -> Image.Image:
        """Decode a base64 string to PIL Image."""
        # Handle data URL format
        if image_base64.startswith('data:'):
            image_base64 = image_base64.split(',')[1]
        
        image_data = base64.b64decode(image_base64)
        return Image.open(BytesIO(image_data)).convert('RGB')
    
    def _encode_image_base64(self, image: Image.Image, format: str = 'PNG') -> str:
        """Encode PIL Image to base64 string."""
        buffer = BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def generate_depth_map(self, image_base64: str, max_size: int = 768) -> Tuple[np.ndarray, Image.Image]:
        """
        Generate a depth map from an image using MiDaS.
        
        Args:
            image_base64: Base64 encoded image
            max_size: Maximum dimension for processing (768 for balance of quality/speed)
            
        Returns:
            Tuple of (depth_array, original_image)
        """
        self._ensure_initialized()
        
        # Decode image
        original_image = self._decode_base64_image(image_base64)
        
        # Resize for processing - balance between quality and speed
        width, height = original_image.size
        if max(width, height) > max_size:
            scale = max_size / max(width, height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            print(f"[Depth] Resizing image from {width}x{height} to {new_width}x{new_height}")
            original_image = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        img_array = np.array(original_image)
        
        # Apply transform
        print("[Depth] Applying MiDaS transform...")
        input_batch = self.transform(img_array).to(self.device)
        
        # Run inference
        print("[Depth] Running depth estimation inference...")
        with torch.no_grad():
            prediction = self.model(input_batch)
            
            # Resize to original size
            prediction = F.interpolate(
                prediction.unsqueeze(1),
                size=img_array.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        
        # Convert to numpy and normalize
        print("[Depth] Processing depth map...")
        depth_map = prediction.cpu().numpy()
        
        # Normalize depth map to 0-1 range
        depth_min = depth_map.min()
        depth_max = depth_map.max()
        if depth_max - depth_min > 0:
            depth_map = (depth_map - depth_min) / (depth_max - depth_min)
        
        return depth_map, original_image
    
    def depth_map_to_image(self, depth_map: np.ndarray) -> str:
        """Convert depth map to a viewable grayscale image (base64)."""
        # Convert to 8-bit grayscale
        depth_visual = (depth_map * 255).astype(np.uint8)
        depth_image = Image.fromarray(depth_visual, mode='L')
        return f"data:image/png;base64,{self._encode_image_base64(depth_image)}"
    
    def create_mesh_from_depth(
        self, 
        image_base64: str, 
        depth_map: np.ndarray,
        depth_scale: float = 0.8,
        simplify: bool = True
    ) -> str:
        """
        Create a 3D mesh from a depth map using a grid-based approach.
        This creates a clean relief mesh without Poisson artifacts.
        
        Args:
            image_base64: Base64 encoded original image (for texture)
            depth_map: Normalized depth map array (0-1)
            depth_scale: Scale factor for depth (0.8 = visible 3D relief)
            simplify: Whether to simplify the mesh for smaller file size
            
        Returns:
            Path to the saved GLB file
        """
        if not _open3d_available:
            raise RuntimeError("Open3D is not installed. Run: pip install open3d")
        
        # Decode texture image
        texture_image = self._decode_base64_image(image_base64)
        texture_array = np.array(texture_image)
        
        height, width = depth_map.shape
        print(f"[Mesh] Creating grid mesh from {width}x{height} depth map...")
        
        # Use step=1 for high quality (every pixel becomes a vertex)
        step = 1
        
        # Calculate grid dimensions
        grid_h = height // step
        grid_w = width // step
        print(f"[Mesh] Grid size: {grid_w}x{grid_h} = {grid_w * grid_h} vertices")
        
        # Aspect ratio for proper proportions
        aspect = width / height
        
        # Create vertices array
        vertices = []
        colors = []
        
        print(f"[Mesh] ORIENTATION: Building on XZ plane, then rotating to vertical")
        print(f"[Mesh] Depth scale: {depth_scale}")
        print(f"[Mesh] Aspect ratio: {aspect}")
        
        for y in range(0, height, step):
            for x in range(0, width, step):
                # MiDaS: higher depth values = closer to camera
                depth_value = depth_map[y, x]
                
                # Build mesh on XZ plane first (horizontal), then rotate to vertical
                # X = horizontal (left-right)
                # Y = depth NEGATED (so after rotation it goes FORWARD)
                # Z = image vertical position
                
                vx = ((x / width) - 0.5) * aspect  # X = horizontal
                vy = -depth_value * depth_scale    # Y = NEGATIVE depth (will flip to +Z forward)
                vz = 0.5 - (y / height)            # Z = image vertical (top=+0.5)
                
                vertices.append([vx, vy, vz])
                
                # Get color from texture
                color = texture_array[y, x] / 255.0
                colors.append(color)
        
        vertices = np.array(vertices)
        colors = np.array(colors)
        
        # Create triangles for a grid mesh (2 triangles per grid cell)
        print("[Mesh] Creating triangle faces...")
        triangles = []
        
        for y in range(grid_h - 1):
            for x in range(grid_w - 1):
                # Get the 4 corners of this grid cell
                v0 = y * grid_w + x          # top-left
                v1 = y * grid_w + (x + 1)    # top-right
                v2 = (y + 1) * grid_w + x    # bottom-left
                v3 = (y + 1) * grid_w + (x + 1)  # bottom-right
                
                # Create 2 triangles for this cell
                # Triangle 1: top-left, bottom-left, top-right
                triangles.append([v0, v2, v1])
                # Triangle 2: top-right, bottom-left, bottom-right
                triangles.append([v1, v2, v3])
        
        triangles = np.array(triangles)
        print(f"[Mesh] Created {len(triangles)} triangles")
        
        # Create Open3D mesh
        mesh = o3d.geometry.TriangleMesh()
        mesh.vertices = o3d.utility.Vector3dVector(vertices)
        mesh.triangles = o3d.utility.Vector3iVector(triangles)
        mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
        
        # ROTATE mesh from XZ plane (horizontal) to XY plane (vertical)
        # Rotate -90 degrees around X axis:
        # - Y (negative depth) -> -Z (positive depth forward) ✓
        # - Z (image vertical) -> Y (up) ✓
        print("[Mesh] Rotating mesh to VERTICAL orientation...")
        R = mesh.get_rotation_matrix_from_xyz((-np.pi/2, 0, 0))
        mesh.rotate(R, center=(0, 0, 0))
        
        # Compute normals for proper lighting
        print("[Mesh] Computing normals...")
        mesh.compute_vertex_normals()
        
        # DISABLED SIMPLIFICATION for maximum quality
        # Keep all triangles for best detail
        print(f"[Mesh] Keeping all {len(mesh.triangles)} triangles (no simplification)")
        
        # Generate unique ID and save
        mesh_id = f"mesh_{uuid.uuid4().hex[:12]}"
        mesh_path = os.path.join(self.meshes_dir, f"{mesh_id}.glb")
        
        # Save as GLB (binary glTF)
        print(f"[Mesh] Saving to {mesh_path}...")
        o3d.io.write_triangle_mesh(mesh_path, mesh)
        print(f"[Mesh] Complete! Mesh ID: {mesh_id}")
        
        return mesh_id, mesh_path
    
    async def generate_mesh_from_image(self, image_base64: str) -> dict:
        """
        Complete pipeline: image -> depth map -> 3D mesh.
        
        Args:
            image_base64: Base64 encoded room photo
            
        Returns:
            Dictionary with mesh_id, mesh_url, and depth_map_url
        """
        import time
        start_time = time.time()
        
        print("[Pipeline] Starting mesh generation pipeline...")
        
        # Generate depth map
        depth_map, original_image = self.generate_depth_map(image_base64)
        depth_time = time.time()
        print(f"[Pipeline] Depth map generated in {depth_time - start_time:.1f}s")
        
        # Convert depth map to viewable image
        depth_map_url = self.depth_map_to_image(depth_map)
        
        # Create 3D mesh (pass the resized image, not original base64)
        # Re-encode the resized image for mesh creation
        resized_base64 = self._encode_image_base64(original_image, 'PNG')
        mesh_id, mesh_path = self.create_mesh_from_depth(resized_base64, depth_map)
        
        total_time = time.time() - start_time
        print(f"[Pipeline] Complete! Total time: {total_time:.1f}s")
        
        return {
            "mesh_id": mesh_id,
            "mesh_path": mesh_path,
            "depth_map_url": depth_map_url,
            "original_size": {
                "width": original_image.width,
                "height": original_image.height
            }
        }
    
    def get_mesh_path(self, mesh_id: str) -> Optional[str]:
        """Get the file path for a mesh by ID."""
        mesh_path = os.path.join(self.meshes_dir, f"{mesh_id}.glb")
        if os.path.exists(mesh_path):
            return mesh_path
        return None
    
    def delete_mesh(self, mesh_id: str) -> bool:
        """Delete a mesh file."""
        mesh_path = self.get_mesh_path(mesh_id)
        if mesh_path and os.path.exists(mesh_path):
            os.remove(mesh_path)
            return True
        return False
    
    def list_meshes(self) -> list:
        """List all generated meshes."""
        meshes = []
        if os.path.exists(self.meshes_dir):
            for filename in os.listdir(self.meshes_dir):
                if filename.endswith('.glb'):
                    mesh_id = filename[:-4]  # Remove .glb extension
                    mesh_path = os.path.join(self.meshes_dir, filename)
                    meshes.append({
                        "mesh_id": mesh_id,
                        "path": mesh_path,
                        "size": os.path.getsize(mesh_path)
                    })
        return meshes


# Singleton instance
depth_service = DepthService()
