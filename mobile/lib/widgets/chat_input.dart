import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';
import '../theme/app_theme.dart';
import 'app_control.dart';
import 'platform_image.dart';
import 'web_camera/web_camera_capture.dart';

/// Design-studio composer. Styling comes from [AppTheme] / ThemeData.
class ChatInput extends StatefulWidget {
  final Function(String message) onSend;
  final Function(File image) onImageSelected;
  final File? selectedImage;
  final VoidCallback? onClearImage;
  final bool isLoading;
  final String? roomHint;

  const ChatInput({
    super.key,
    required this.onSend,
    required this.onImageSelected,
    this.selectedImage,
    this.onClearImage,
    this.isLoading = false,
    this.roomHint,
  });

  @override
  State<ChatInput> createState() => ChatInputState();
}

class ChatInputState extends State<ChatInput> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  final ImagePicker _picker = ImagePicker();

  bool get _canSend =>
      (_controller.text.trim().isNotEmpty || widget.selectedImage != null) &&
      !widget.isLoading;

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void setDraft(String text) {
    _controller.text = text;
    _controller.selection = TextSelection.fromPosition(
      TextPosition(offset: text.length),
    );
    setState(() {});
    focusField();
  }

  void focusField() {
    _focusNode.requestFocus();
  }

  void _sendMessage() {
    if (!_canSend) return;
    widget.onSend(_controller.text.trim());
    _controller.clear();
    setState(() {});
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      // Desktop browsers can't open a real camera via image_picker —
      // they fall back to a file dialog. Use getUserMedia on web instead.
      if (source == ImageSource.camera && kIsWeb && supportsWebcamCapture) {
        final blobUrl = await capturePhotoWithWebcam(context);
        if (blobUrl != null && mounted) {
          widget.onImageSelected(File(blobUrl));
        }
        return;
      }

      final XFile? image = await _picker.pickImage(
        source: source,
        maxWidth: 1920,
        maxHeight: 1920,
        imageQuality: 85,
        preferredCameraDevice: CameraDevice.rear,
      );
      if (image != null) {
        widget.onImageSelected(File(image.path));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error picking image: $e'),
            backgroundColor: AppTheme.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  void showImageSourcePicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppTheme.radiusLg),
        ),
      ),
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 3,
                  color: AppTheme.border,
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Add room photo',
                style: GoogleFonts.interTight(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.ink,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                kIsWeb
                    ? 'Use your webcam or upload a photo from your files'
                    : 'Take a new photo or choose from gallery',
                style: GoogleFonts.interTight(
                  fontSize: 13,
                  color: AppTheme.textMuted,
                ),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: _SourceOption(
                      icon: Icons.camera_alt_outlined,
                      label: kIsWeb ? 'Webcam' : 'Camera',
                      onTap: () {
                        Navigator.pop(context);
                        _pickImage(ImageSource.camera);
                      },
                    ),
                  ),
                  SizedBox(width: AppTheme.controlGap + 2),
                  Expanded(
                    child: _SourceOption(
                      icon: Icons.photo_library_outlined,
                      label: kIsWeb ? 'Upload' : 'Gallery',
                      onTap: () {
                        Navigator.pop(context);
                        _pickImage(ImageSource.gallery);
                      },
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final hint = widget.selectedImage != null
        ? 'Describe the changes you want…'
        : widget.roomHint != null
            ? 'Describe your ${widget.roomHint!.toLowerCase()}…'
            : 'Describe your dream room…';

    return Container(
      padding: EdgeInsets.fromLTRB(
        14,
        10,
        14,
        MediaQuery.of(context).padding.bottom + 10,
      ),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        border: Border(top: BorderSide(color: AppTheme.gridLine)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (widget.selectedImage != null) ...[
            Row(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: AppTheme.controlDecoration(
                    color: AppTheme.surface,
                    borderColor: AppTheme.ink,
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: PlatformFileImage(
                    file: widget.selectedImage!,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => const Icon(
                      Icons.image_outlined,
                      color: AppTheme.textMuted,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Photo attached',
                        style: GoogleFonts.interTight(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.ink,
                        ),
                      ),
                      Text(
                        'Describe how to redesign it',
                        style: GoogleFonts.interTight(
                          fontSize: 12,
                          color: AppTheme.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
                AppIconControl(
                  icon: Icons.close_rounded,
                  onTap: widget.onClearImage,
                  tooltip: 'Remove photo',
                ),
              ],
            ),
            const SizedBox(height: 10),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              AppIconControl(
                icon: Icons.add_photo_alternate_outlined,
                onTap: widget.isLoading ? null : showImageSourcePicker,
                tooltip: 'Add photo',
              ),
              SizedBox(width: AppTheme.controlGap),
              Expanded(
                child: AppControlField(
                  controller: _controller,
                  focusNode: _focusNode,
                  hintText: hint,
                  enabled: !widget.isLoading,
                  textCapitalization: TextCapitalization.sentences,
                  onChanged: (_) => setState(() {}),
                  onSubmitted: (_) => _sendMessage(),
                ),
              ),
              SizedBox(width: AppTheme.controlGap),
              AppIconControl(
                icon: Icons.arrow_upward_rounded,
                onTap: _canSend ? _sendMessage : null,
                emphasized: _canSend,
                loading: widget.isLoading,
                tooltip: 'Send',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SourceOption extends StatefulWidget {
  const _SourceOption({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  State<_SourceOption> createState() => _SourceOptionState();
}

class _SourceOptionState extends State<_SourceOption> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 140),
          padding: const EdgeInsets.symmetric(vertical: 20),
          decoration: AppTheme.controlDecoration(
            color: _hovered ? AppTheme.panelTone : AppTheme.inputBackground,
          ),
          child: Column(
            children: [
              Icon(widget.icon, size: 24, color: AppTheme.ink),
              const SizedBox(height: 10),
              Text(
                widget.label,
                style: GoogleFonts.interTight(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.ink,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
