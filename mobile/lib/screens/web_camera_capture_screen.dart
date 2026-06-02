import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

import '../theme/app_theme.dart';
import '../utils/web_camera_capture.dart';

class WebCameraCaptureScreen extends StatefulWidget {
  const WebCameraCaptureScreen({super.key});

  @override
  State<WebCameraCaptureScreen> createState() => _WebCameraCaptureScreenState();
}

class _WebCameraCaptureScreenState extends State<WebCameraCaptureScreen> {
  final WebCameraCaptureController _camera = WebCameraCaptureController();

  bool _isStarting = false;
  bool _isCapturing = false;
  bool _isCameraReady = false;
  String? _error;
  String? _diagnostics;

  @override
  void dispose() {
    _camera.dispose();
    super.dispose();
  }

  Future<void> _startCamera() async {
    setState(() {
      _isStarting = true;
      _error = null;
      _diagnostics = null;
    });

    try {
      await _camera.start();
      if (!mounted) return;
      setState(() {
        _isCameraReady = true;
        _isStarting = false;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _camera.playPreview();
      });
    } catch (e) {
      if (!mounted) return;
      final diagnostics = await _camera.diagnosticsForError(e);
      if (!mounted) return;
      setState(() {
        _isStarting = false;
        _error = _cameraErrorMessage(e);
        _diagnostics = diagnostics;
      });
    }
  }

  Future<void> _capturePhoto() async {
    setState(() {
      _isCapturing = true;
      _error = null;
      _diagnostics = null;
    });

    try {
      final XFile image = await _camera.capture();
      if (!mounted) return;
      Navigator.pop(context, image);
    } catch (e) {
      if (!mounted) return;
      final diagnostics = await _camera.diagnosticsForError(e);
      if (!mounted) return;
      setState(() {
        _isCapturing = false;
        _error = 'Could not capture photo: $e';
        _diagnostics = diagnostics;
      });
    }
  }

  String _cameraErrorMessage(Object error) {
    final message = error.toString();
    if (message.contains('NotAllowedError') || message.contains('Permission')) {
      return 'Camera access is blocked for this site. Tap the browser address bar/site settings, allow Camera for this page, then try again.';
    }
    if (message.contains('NotFoundError')) {
      return 'No camera was found on this device.';
    }
    if (message.contains('NotReadableError')) {
      return 'The camera is already in use by another app or browser tab.';
    }
    return 'Could not open the camera: $message';
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
              child: _isCameraReady ? _buildCameraPreview() : _buildPermissionPrompt(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAppBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.close_rounded),
            style: IconButton.styleFrom(
              backgroundColor: AppTheme.surface,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              'Take Room Photo',
              style: GoogleFonts.dmSans(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPermissionPrompt() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 96,
              height: 96,
              decoration: BoxDecoration(
                color: AppTheme.primaryColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Icon(
                Icons.camera_alt_rounded,
                color: AppTheme.primaryColor,
                size: 48,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Allow camera access',
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSans(
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Your browser will ask for permission so you can take a room photo directly in the web app.',
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSans(
                fontSize: 15,
                height: 1.4,
                color: AppTheme.textMuted,
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppTheme.error.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppTheme.error.withOpacity(0.2)),
                ),
                child: Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.dmSans(
                    fontSize: 13,
                    color: AppTheme.error,
                  ),
                ),
              ),
              if (_diagnostics != null) ...[
                const SizedBox(height: 12),
                _buildDiagnosticsBox(),
              ],
            ],
            const SizedBox(height: 28),
            ElevatedButton.icon(
              onPressed: _isStarting ? null : _startCamera,
              icon: _isStarting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.camera_alt_rounded),
              label: Text(_isStarting ? 'Opening Camera...' : 'Allow Camera'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                disabledBackgroundColor: AppTheme.primaryColor.withOpacity(0.5),
                padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 16),
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

  Widget _buildCameraPreview() {
    return Column(
      children: [
        Expanded(
          child: Container(
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.black,
              borderRadius: BorderRadius.circular(20),
              boxShadow: AppTheme.cardShadow,
            ),
            clipBehavior: Clip.antiAlias,
            child: _camera.buildPreview(),
          ),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(
              _error!,
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSans(color: AppTheme.error),
            ),
          ),
        if (_diagnostics != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: _buildDiagnosticsBox(),
          ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _isCapturing ? null : () => Navigator.pop(context),
                  icon: const Icon(Icons.close_rounded),
                  label: const Text('Cancel'),
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
                  onPressed: _isCapturing ? null : _capturePhoto,
                  icon: _isCapturing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.camera_rounded),
                  label: Text(_isCapturing ? 'Capturing...' : 'Capture Photo'),
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

  Widget _buildDiagnosticsBox() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.inputBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: SelectableText(
        _diagnostics!,
        style: GoogleFonts.dmMono(
          fontSize: 11,
          color: AppTheme.textSecondary,
        ),
      ),
    );
  }
}
