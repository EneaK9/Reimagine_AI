import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../providers/chat_provider.dart';
import '../providers/scene_provider.dart';
import '../utils/scene_editor_launcher.dart';
import '../widgets/platform_image.dart';
import 'chat_screen.dart';

/// Room scan: photo -> editable 3D room.
///
/// Right after the photo is taken the backend builds a structured scene
/// (room shell + separate furniture objects) and the interactive editor
/// opens. The older depth-relief mesh is only an optional
/// "Quick depth preview"; the main flow doesn't depend on it.
class RoomScanScreen extends StatefulWidget {
  const RoomScanScreen({super.key});

  @override
  State<RoomScanScreen> createState() => _RoomScanScreenState();
}

enum _ScanStage { capturing, building, ready, failed }

class _RoomScanScreenState extends State<RoomScanScreen> {
  /// Rough timeline of the scene pipeline (seconds) for the progress steps.
  static const _buildSteps = [
    (label: 'Measuring the room', startsAt: 0),
    (label: 'Finding furniture', startsAt: 12),
    (label: 'Building 3D scene', startsAt: 35),
  ];

  final ImagePicker _picker = ImagePicker();
  final ApiService _apiService = ApiService();

  _ScanStage _stage = _ScanStage.capturing;
  File? _capturedImage;
  String? _error;
  String? _sceneId;

  // Conversation the scan was started from (see conversationGeneration)
  late final int _startConversation;

  // Build progress
  Timer? _progressTimer;
  int _elapsedSeconds = 0;
  int _buildRun = 0;

  // Optional legacy depth-relief preview
  bool _isDepthLoading = false;
  bool _showDepthPreview = false;
  String? _meshUrl;
  String? _meshId;
  String? _depthMapUrl;

  @override
  void initState() {
    super.initState();
    _startConversation = context.read<ChatProvider>().conversationGeneration;
    // Open camera immediately when screen loads
    WidgetsBinding.instance.addPostFrameCallback((_) => _capturePhoto());
  }

  @override
  void dispose() {
    _progressTimer?.cancel();
    super.dispose();
  }

  Future<void> _capturePhoto() async {
    final hadPhoto = _capturedImage != null;
    final XFile? image;
    try {
      // Desktop targets (macOS) have no camera in image_picker: pick a file.
      final source = _picker.supportsImageSource(ImageSource.camera)
          ? ImageSource.camera
          : ImageSource.gallery;
      image = await _picker.pickImage(
        source: source,
        maxWidth: 1920,
        maxHeight: 1920,
        imageQuality: 85,
      );
    } catch (e) {
      if (!mounted) return;
      if (hadPhoto) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not open the camera: $e')),
        );
      } else {
        setState(() {
          _stage = _ScanStage.failed;
          _error = 'Could not open the camera: $e';
        });
      }
      return;
    }
    if (!mounted) return;

    if (image == null) {
      // Cancelled: leave on the first shot, keep the current result on retake.
      if (!hadPhoto) Navigator.pop(context);
      return;
    }

    final photo = File(image.path);
    setState(() {
      _capturedImage = photo;
      _sceneId = null;
      _meshUrl = null;
      _meshId = null;
      _depthMapUrl = null;
      _showDepthPreview = false;
    });
    await _buildEditableRoom();
  }

  /// Build the structured, editable 3D room from the photo and open the
  /// editor. Retry calls this again with the same photo.
  Future<void> _buildEditableRoom() async {
    final photo = _capturedImage;
    if (photo == null || _stage == _ScanStage.building) return;
    final run = ++_buildRun;
    final sceneProvider = context.read<SceneProvider>();
    final chat = context.read<ChatProvider>();
    final stillInStartConversation =
        chat.conversationGeneration == _startConversation;

    _startProgress();
    setState(() {
      _stage = _ScanStage.building;
      _error = null;
      _sceneId = null;
    });

    Map<String, dynamic> sceneResponse;
    try {
      sceneResponse = await _apiService.generateSceneFromPhoto(
        photo,
        // Lets the backend link the scene to the conversation it came from
        // (only once that conversation exists on the backend).
        conversationId:
            stillInStartConversation ? chat.persistedConversationId : null,
      );
      if (sceneResponse['scene_id'] is! String) {
        throw ApiException('The server did not return a 3D room.');
      }
      if (!mounted || run != _buildRun) return;
      await sceneProvider.setGeneratedScene(sceneResponse);
    } catch (e) {
      if (!mounted || run != _buildRun) return;
      _stopProgress();
      setState(() {
        _stage = _ScanStage.failed;
        _error = e.toString();
      });
      return;
    }
    if (!mounted || run != _buildRun) return;

    final sceneId = sceneResponse['scene_id'] as String;
    // The conversation this scan started from now owns the 3D room (a draft
    // gets linked on the backend by its first message, which sends scene_id).
    if (chat.conversationGeneration == _startConversation) {
      chat.setCurrentScene(sceneId);
    }
    _stopProgress();
    setState(() {
      _stage = _ScanStage.ready;
      _sceneId = sceneId;
    });

    // Mobile opens the editor right away. On web it opens in a new tab,
    // which browsers only allow from a tap (popup blockers), so the ready
    // screen shows an "Open 3D editor" button instead.
    if (!kIsWeb) await openSceneEditor(context);
  }

  void _startProgress() {
    _progressTimer?.cancel();
    _elapsedSeconds = 0;
    _progressTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _elapsedSeconds++);
    });
  }

  void _stopProgress() {
    _progressTimer?.cancel();
    _progressTimer = null;
  }

  /// The editor opens in a new browser tab on web.
  IconData get _openEditorIcon =>
      kIsWeb ? Icons.open_in_new_rounded : Icons.view_in_ar_rounded;

  /// Called straight from the button tap, so the web tab isn't blocked.
  void _openEditor() {
    final sceneId = _sceneId;
    if (sceneId == null) return;
    // Mobile edits the scene already held by the provider (no refetch)
    // unless another scene has replaced it since.
    final alreadyLoaded = context.read<SceneProvider>().sceneId == sceneId;
    openSceneEditor(
      context,
      sceneId: kIsWeb || !alreadyLoaded ? sceneId : null,
    );
  }

  /// Legacy 2.5D depth-relief mesh (optional; independent of the 3D room).
  Future<void> _loadDepthPreview() async {
    final photo = _capturedImage;
    if (photo == null || _isDepthLoading) return;
    if (_meshUrl != null) {
      setState(() => _showDepthPreview = true);
      return;
    }

    setState(() => _isDepthLoading = true);
    try {
      final result = await _apiService.generateMeshFromPhoto(photo);
      if (!mounted || photo != _capturedImage) return;
      setState(() {
        _meshId = result['mesh_id'];
        _meshUrl = result['mesh_url'];
        _depthMapUrl = result['depth_map_url'];
        _showDepthPreview = _meshUrl != null;
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Depth preview unavailable: $e')),
      );
    } finally {
      if (mounted) setState(() => _isDepthLoading = false);
    }
  }

  void _editInChat() {
    final chatProvider = context.read<ChatProvider>();
    // Continue the conversation the scan was started from; start a new one
    // only if the chat has moved on since.
    if (chatProvider.conversationGeneration != _startConversation) {
      chatProvider.startNewConversation();
    }

    // Attach the 3D room so chat edits apply to it (and the backend links it)
    if (_sceneId != null) chatProvider.setCurrentScene(_sceneId);

    // Set the mesh info so chat can edit it
    if (_meshId != null && _meshUrl != null) {
      chatProvider.setCurrentMesh(_meshId, _meshUrl);
    }

    // Only set the image if we don't have a mesh - otherwise we're editing the mesh
    if (_capturedImage != null && _meshId == null) {
      chatProvider.setSelectedImage(_capturedImage);
    }

    // Back to the chat this scan was opened from (keeps its state).
    final navigator = Navigator.of(context);
    if (navigator.canPop()) {
      navigator.pop();
    } else {
      navigator.pushReplacement(
        MaterialPageRoute(
          builder: (_) => const ChatScreen(resetConversation: false),
        ),
      );
    }
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

  String get _subtitle {
    if (_showDepthPreview && _meshUrl != null) return 'Rotate to explore';
    return switch (_stage) {
      _ScanStage.capturing => 'Take a photo of your room',
      _ScanStage.building => 'Building your 3D room…',
      _ScanStage.ready => 'Your 3D room is ready',
      _ScanStage.failed => 'Something went wrong',
    };
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
                  '3D Room Scan',
                  style: GoogleFonts.dmSans(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  _subtitle,
                  style: GoogleFonts.dmSans(
                    fontSize: 12,
                    color: AppTheme.textMuted,
                  ),
                ),
              ],
            ),
          ),
          if (_capturedImage != null && _stage != _ScanStage.building) ...[
            IconButton(
              onPressed: _capturePhoto,
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
    if (_showDepthPreview && _meshUrl != null) return _buildDepthPreview();
    return switch (_stage) {
      _ScanStage.capturing => _buildWaitingState(),
      _ScanStage.building => _buildBuildingState(),
      _ScanStage.ready => _buildReadyState(),
      _ScanStage.failed => _buildFailedState(),
    };
  }

  ButtonStyle get _primaryButtonStyle => ElevatedButton.styleFrom(
        backgroundColor: AppTheme.primaryColor,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
        ),
      );

  ButtonStyle get _outlinedButtonStyle => OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(vertical: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
        ),
      );

  Widget _buildWaitingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              color: AppTheme.primaryColor.withValues(alpha: 0.1),
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

  Widget _buildBuildingState() {
    final activeStep =
        _buildSteps.lastIndexWhere((s) => _elapsedSeconds >= s.startsAt);
    final minutes = _elapsedSeconds ~/ 60;
    final seconds = (_elapsedSeconds % 60).toString().padLeft(2, '0');

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
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
                    PlatformFileImage(
                      file: _capturedImage!,
                      fit: BoxFit.cover,
                      width: 200,
                      height: 200,
                    ),
                    Container(
                      color: Colors.black.withValues(alpha: 0.5),
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
            ],
            Text(
              'Building your 3D room',
              style: GoogleFonts.dmSans(
                fontSize: 20,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'This usually takes 20–90 seconds · $minutes:$seconds',
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSans(
                fontSize: 14,
                color: AppTheme.textMuted,
              ),
            ),
            const SizedBox(height: 24),
            // Progress steps
            Container(
              constraints: const BoxConstraints(maxWidth: 360),
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.border),
              ),
              child: Column(
                children: [
                  for (var i = 0; i < _buildSteps.length; i++)
                    _buildProgressStep(
                      _buildSteps[i].label,
                      done: i < activeStep,
                      active: i == activeStep,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressStep(
    String label, {
    required bool done,
    required bool active,
  }) {
    final reached = done || active;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: reached ? AppTheme.primaryColor : AppTheme.border,
              shape: BoxShape.circle,
            ),
            child: active
                ? const Padding(
                    padding: EdgeInsets.all(6),
                    child: CircularProgressIndicator(
                      color: Colors.white,
                      strokeWidth: 2,
                    ),
                  )
                : done
                    ? const Icon(Icons.check, size: 14, color: Colors.white)
                    : null,
          ),
          const SizedBox(width: 12),
          Text(
            label,
            style: GoogleFonts.dmSans(
              fontSize: 14,
              color: reached ? AppTheme.textPrimary : AppTheme.textMuted,
              fontWeight: active ? FontWeight.w500 : FontWeight.normal,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBadge(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white, size: 16),
          const SizedBox(width: 6),
          Text(
            label,
            style: GoogleFonts.dmSans(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEditInChatButton({required bool primary}) {
    const icon = Icon(Icons.edit_rounded);
    const label = Text('Edit in Chat');
    return primary
        ? ElevatedButton.icon(
            onPressed: _editInChat,
            icon: icon,
            label: label,
            style: _primaryButtonStyle,
          )
        : OutlinedButton.icon(
            onPressed: _editInChat,
            icon: icon,
            label: label,
            style: _outlinedButtonStyle,
          );
  }

  Widget _buildDepthPreviewButton() {
    return TextButton.icon(
      onPressed: _isDepthLoading ? null : _loadDepthPreview,
      icon: _isDepthLoading
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.layers_outlined, size: 18),
      label: Text(
        _isDepthLoading ? 'Generating depth preview…' : 'Quick depth preview',
      ),
      style: TextButton.styleFrom(foregroundColor: AppTheme.textSecondary),
    );
  }

  Widget _buildReadyState() {
    return Column(
      children: [
        Expanded(
          child: Container(
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.inputBackground,
              borderRadius: BorderRadius.circular(20),
              boxShadow: AppTheme.cardShadow,
            ),
            clipBehavior: Clip.antiAlias,
            child: Stack(
              fit: StackFit.expand,
              children: [
                if (_capturedImage != null)
                  PlatformFileImage(
                    file: _capturedImage!,
                    fit: BoxFit.cover,
                  ),
                Positioned(
                  top: 16,
                  left: 16,
                  child: _buildBadge(
                    Icons.check_circle_rounded,
                    '3D room ready',
                  ),
                ),
              ],
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          child: Column(
            children: [
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _openEditor,
                  icon: Icon(_openEditorIcon),
                  label: const Text('Open 3D editor'),
                  style: _primaryButtonStyle,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _capturePhoto,
                      icon: const Icon(Icons.camera_alt_rounded),
                      label: const Text('New Photo'),
                      style: _outlinedButtonStyle,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    flex: 2,
                    child: _buildEditInChatButton(primary: false),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              _buildDepthPreviewButton(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildFailedState() {
    final canRetry = _capturedImage != null;
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 100,
                height: 100,
                decoration: BoxDecoration(
                  color: AppTheme.error.withValues(alpha: 0.1),
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
                canRetry
                    ? "Couldn't build your 3D room"
                    : 'Something went wrong',
                textAlign: TextAlign.center,
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
              if (canRetry) ...[
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _buildEditableRoom,
                    icon: const Icon(Icons.refresh_rounded),
                    label: const Text('Retry'),
                    style: _primaryButtonStyle,
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: _capturePhoto,
                    icon: const Icon(Icons.camera_alt_rounded),
                    label: const Text('Retake photo'),
                    style: _outlinedButtonStyle,
                  ),
                ),
                const SizedBox(height: 4),
                _buildDepthPreviewButton(),
              ] else
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _capturePhoto,
                    icon: const Icon(Icons.camera_alt_rounded),
                    label: const Text('Take photo'),
                    style: _primaryButtonStyle,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDepthPreview() {
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
              color: AppTheme.inputBackground,
              borderRadius: BorderRadius.circular(20),
              boxShadow: AppTheme.cardShadow,
            ),
            clipBehavior: Clip.antiAlias,
            child: Stack(
              children: [
                ModelViewer(
                  src: fullMeshUrl,
                  alt: "Room depth preview",
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
                  backgroundColor: AppTheme.inputBackground,
                ),
                Positioned(
                  top: 16,
                  left: 16,
                  child: _buildBadge(Icons.layers_outlined, 'Depth preview'),
                ),
              ],
            ),
          ),
        ),

        // Depth map preview
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
                  child: PlatformFileImage(
                    file: _capturedImage!,
                    fit: BoxFit.cover,
                  ),
                ),
                const SizedBox(width: 8),
                const Icon(Icons.arrow_forward, size: 16, color: AppTheme.textMuted),
                const SizedBox(width: 8),
                // Depth map thumbnail
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    color: AppTheme.border,
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: Image.network(
                    _depthMapUrl!,
                    fit: BoxFit.cover,
                    errorBuilder: (_, _, _) => const Icon(Icons.image),
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
          child: Column(
            children: [
              if (_sceneId != null) ...[
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _openEditor,
                    icon: Icon(_openEditorIcon),
                    label: const Text('Open 3D editor'),
                    style: _primaryButtonStyle,
                  ),
                ),
                const SizedBox(height: 12),
              ],
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () =>
                          setState(() => _showDepthPreview = false),
                      icon: const Icon(Icons.arrow_back_rounded),
                      label: const Text('Back'),
                      style: _outlinedButtonStyle,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    flex: 2,
                    child: _buildEditInChatButton(primary: _sceneId == null),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}
