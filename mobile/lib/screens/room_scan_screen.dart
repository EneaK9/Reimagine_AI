import 'dart:io';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../providers/chat_provider.dart';
import 'chat_screen.dart';

/// Quick Scan Screen - Photo to 3D using depth estimation
/// Replaces the Unity-based AR scanning with a simpler photo-based approach
class RoomScanScreen extends StatefulWidget {
  const RoomScanScreen({super.key});

  @override
  State<RoomScanScreen> createState() => _RoomScanScreenState();
}

class _RoomScanScreenState extends State<RoomScanScreen> {
  final ImagePicker _picker = ImagePicker();
  final ApiService _apiService = ApiService();
  
  // State
  File? _capturedImage;
  String? _meshUrl;
  String? _meshId;
  String? _depthMapUrl;
  bool _isGenerating = false;
  String? _error;
  
  // Generation progress
  String _progressMessage = '';

  @override
  void initState() {
    super.initState();
    // Open camera immediately when screen loads
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _openCamera();
    });
  }

  Future<void> _openCamera() async {
    try {
      final XFile? image = await _picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1920,
        maxHeight: 1920,
        imageQuality: 85,
      );
      
      if (image != null) {
        setState(() {
          _capturedImage = File(image.path);
          _error = null;
        });
        
        // Automatically start mesh generation
        await _generateMesh();
      } else {
        // User cancelled camera - go back
        if (mounted) {
          Navigator.pop(context);
        }
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to capture image: $e';
      });
    }
  }

  Future<void> _generateMesh() async {
    if (_capturedImage == null) return;
    
    setState(() {
      _isGenerating = true;
      _error = null;
      _progressMessage = 'Analyzing image...';
    });
    
    try {
      // Update progress
      setState(() {
        _progressMessage = 'Generating depth map...';
      });
      
      // Call API to generate mesh
      final result = await _apiService.generateMeshFromPhoto(_capturedImage!);
      
      setState(() {
        _progressMessage = 'Building 3D mesh...';
      });
      
      // Small delay for UX
      await Future.delayed(const Duration(milliseconds: 500));
      
      setState(() {
        _meshId = result['mesh_id'];
        _meshUrl = result['mesh_url'];
        _depthMapUrl = result['depth_map_url'];
        _isGenerating = false;
        _progressMessage = '';
      });
      
    } catch (e) {
      setState(() {
        _isGenerating = false;
        _error = 'Failed to generate 3D view: $e';
        _progressMessage = '';
      });
    }
  }

  void _retakePhoto() {
    setState(() {
      _capturedImage = null;
      _meshUrl = null;
      _meshId = null;
      _depthMapUrl = null;
      _error = null;
    });
    _openCamera();
  }

  void _editInChat() {
    // Navigate to chat with the mesh attached for editing
    final chatProvider = context.read<ChatProvider>();
    chatProvider.startNewConversation();
    
    // Set the mesh info so chat can edit it
    if (_meshId != null && _meshUrl != null) {
      chatProvider.setCurrentMesh(_meshId, _meshUrl);
    }
    
    // Only set the image if we don't have a mesh - otherwise we're editing the mesh
    if (_capturedImage != null && _meshId == null) {
      chatProvider.setSelectedImage(_capturedImage);
    }
    
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => const ChatScreen(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildAppBar(),
            Expanded(
              child: _buildContent(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAppBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back_rounded),
            style: IconButton.styleFrom(
              backgroundColor: AppTheme.surface,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Quick 3D Scan',
                  style: GoogleFonts.dmSans(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  _meshUrl != null 
                      ? 'Rotate to explore' 
                      : 'Take a photo of your room',
                  style: GoogleFonts.dmSans(
                    fontSize: 12,
                    color: AppTheme.textMuted,
                  ),
                ),
              ],
            ),
          ),
          if (_capturedImage != null && !_isGenerating) ...[
            IconButton(
              onPressed: _retakePhoto,
              icon: const Icon(Icons.refresh_rounded),
              tooltip: 'Retake photo',
              style: IconButton.styleFrom(
                backgroundColor: AppTheme.surface,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildContent() {
    if (_error != null) {
      return _buildErrorState();
    }
    
    if (_isGenerating) {
      return _buildLoadingState();
    }
    
    if (_meshUrl != null) {
      return _build3DViewer();
    }
    
    if (_capturedImage != null) {
      return _buildImagePreview();
    }
    
    return _buildWaitingState();
  }

  Widget _buildWaitingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              color: AppTheme.primaryColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(25),
            ),
            child: Icon(
              Icons.camera_alt_rounded,
              size: 50,
              color: AppTheme.primaryColor,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Opening Camera...',
            style: GoogleFonts.dmSans(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Take a photo of your room',
            style: GoogleFonts.dmSans(
              fontSize: 14,
              color: AppTheme.textMuted,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Show captured image as background
          if (_capturedImage != null) ...[
            Container(
              width: 200,
              height: 200,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(20),
                boxShadow: AppTheme.cardShadow,
              ),
              clipBehavior: Clip.antiAlias,
              child: Stack(
                children: [
                  Image.file(
                    _capturedImage!,
                    fit: BoxFit.cover,
                    width: 200,
                    height: 200,
                  ),
                  Container(
                    color: Colors.black.withOpacity(0.5),
                  ),
                  const Center(
                    child: CircularProgressIndicator(
                      color: Colors.white,
                      strokeWidth: 3,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
          ] else ...[
            CircularProgressIndicator(
              color: AppTheme.primaryColor,
              strokeWidth: 3,
            ),
            const SizedBox(height: 32),
          ],
          Text(
            'Generating 3D View',
            style: GoogleFonts.dmSans(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _progressMessage,
            style: GoogleFonts.dmSans(
              fontSize: 14,
              color: AppTheme.textMuted,
            ),
          ),
          const SizedBox(height: 24),
          // Progress steps
          Container(
            padding: const EdgeInsets.all(20),
            margin: const EdgeInsets.symmetric(horizontal: 40),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              children: [
                _buildProgressStep('Analyzing image', _progressMessage.contains('Analyzing')),
                _buildProgressStep('Generating depth map', _progressMessage.contains('depth')),
                _buildProgressStep('Building 3D mesh', _progressMessage.contains('mesh')),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressStep(String label, bool isActive) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: isActive ? AppTheme.primaryColor : AppTheme.border,
              shape: BoxShape.circle,
            ),
            child: isActive
                ? const Padding(
                    padding: EdgeInsets.all(6),
                    child: CircularProgressIndicator(
                      color: Colors.white,
                      strokeWidth: 2,
                    ),
                  )
                : Icon(
                    Icons.check,
                    size: 14,
                    color: AppTheme.textMuted,
                  ),
          ),
          const SizedBox(width: 12),
          Text(
            label,
            style: GoogleFonts.dmSans(
              fontSize: 14,
              color: isActive ? AppTheme.textPrimary : AppTheme.textMuted,
              fontWeight: isActive ? FontWeight.w500 : FontWeight.normal,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImagePreview() {
    return Column(
      children: [
        Expanded(
          child: Container(
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              boxShadow: AppTheme.cardShadow,
            ),
            clipBehavior: Clip.antiAlias,
            child: Image.file(
              _capturedImage!,
              fit: BoxFit.contain,
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _retakePhoto,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retake'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                flex: 2,
                child: ElevatedButton.icon(
                  onPressed: _generateMesh,
                  icon: const Icon(Icons.view_in_ar),
                  label: const Text('Generate 3D'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryColor,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _build3DViewer() {
    // Construct full URL for the mesh
    final fullMeshUrl = _apiService.getFullMeshUrl(_meshUrl!);
    
    return Column(
      children: [
        // 3D Viewer
        Expanded(
          flex: 3,
          child: Container(
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(20),
              boxShadow: AppTheme.cardShadow,
            ),
            clipBehavior: Clip.antiAlias,
            child: Stack(
              children: [
                ModelViewer(
                  src: fullMeshUrl,
                  alt: "Room 3D View",
                  ar: false,
                  autoRotate: false,
                  cameraControls: true,
                  disableZoom: false,
                  // Start from front view, allow full rotation
                  cameraOrbit: "0deg 90deg 1.2m",
                  minCameraOrbit: "-Infinity 0deg 0.3m",  // Allow full horizontal rotation
                  maxCameraOrbit: "Infinity 180deg 3m",   // Allow full vertical rotation
                  fieldOfView: "35deg",
                  interactionPrompt: InteractionPrompt.none,  // Hide the interaction hint
                  backgroundColor: const Color(0xFFF5F5F5),
                ),
                // 3D badge
                Positioned(
                  top: 16,
                  left: 16,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryColor,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.view_in_ar, color: Colors.white, size: 16),
                        const SizedBox(width: 6),
                        Text(
                          '3D View',
                          style: GoogleFonts.dmSans(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        
        // Depth map preview (optional - can be hidden)
        if (_depthMapUrl != null) ...[
          Container(
            height: 80,
            margin: const EdgeInsets.symmetric(horizontal: 16),
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.border),
            ),
            child: Row(
              children: [
                // Original image thumbnail
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: Image.file(
                    _capturedImage!,
                    fit: BoxFit.cover,
                  ),
                ),
                const SizedBox(width: 8),
                const Icon(Icons.arrow_forward, size: 16, color: Colors.grey),
                const SizedBox(width: 8),
                // Depth map thumbnail
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    color: Colors.grey.shade200,
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: Image.network(
                    _depthMapUrl!,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => const Icon(Icons.image),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        'Depth Estimation',
                        style: GoogleFonts.dmSans(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      Text(
                        'AI-generated depth map',
                        style: GoogleFonts.dmSans(
                          fontSize: 10,
                          color: AppTheme.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
        
        // Action buttons
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _retakePhoto,
                  icon: const Icon(Icons.camera_alt_rounded),
                  label: const Text('New Photo'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                flex: 2,
                child: ElevatedButton.icon(
                  onPressed: _editInChat,
                  icon: const Icon(Icons.edit_rounded),
                  label: const Text('Edit in Chat'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryColor,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                color: AppTheme.error.withOpacity(0.1),
                borderRadius: BorderRadius.circular(25),
              ),
              child: Icon(
                Icons.error_outline_rounded,
                size: 50,
                color: AppTheme.error,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Something went wrong',
              style: GoogleFonts.dmSans(
                fontSize: 20,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _error ?? 'Unknown error occurred',
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSans(
                fontSize: 14,
                color: AppTheme.textMuted,
              ),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: _retakePhoto,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try Again'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
