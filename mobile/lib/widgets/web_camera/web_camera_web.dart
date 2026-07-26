// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:convert';
import 'dart:html' as html;
import 'dart:typed_data';
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../theme/app_theme.dart';

bool get supportsWebcamCapture => true;

/// Opens a webcam preview dialog and returns a blob: URL of the captured JPEG.
Future<String?> capturePhotoWithWebcam(BuildContext context) {
  return showDialog<String>(
    context: context,
    barrierDismissible: false,
    builder: (context) => const _WebCameraDialog(),
  );
}

class _WebCameraDialog extends StatefulWidget {
  const _WebCameraDialog();

  @override
  State<_WebCameraDialog> createState() => _WebCameraDialogState();
}

class _WebCameraDialogState extends State<_WebCameraDialog> {
  late final String _viewType;
  html.VideoElement? _video;
  html.MediaStream? _stream;
  String? _error;
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _viewType =
        'reimagine-webcam-${DateTime.now().microsecondsSinceEpoch}';
    _startCamera();
  }

  Future<void> _startCamera() async {
    try {
      final video = html.VideoElement()
        ..autoplay = true
        ..muted = true
        ..setAttribute('playsinline', 'true')
        ..style.objectFit = 'cover'
        ..style.width = '100%'
        ..style.height = '100%'
        ..style.backgroundColor = '#1D1B18';

      html.MediaStream stream;
      try {
        stream = await html.window.navigator.mediaDevices!.getUserMedia({
          'video': {
            'facingMode': 'environment',
            'width': {'ideal': 1920},
            'height': {'ideal': 1080},
          },
          'audio': false,
        });
      } catch (_) {
        // Laptops / denied rear camera — fall back to any webcam.
        stream = await html.window.navigator.mediaDevices!.getUserMedia({
          'video': true,
          'audio': false,
        });
      }

      video.srcObject = stream;
      await video.play();

      ui_web.platformViewRegistry.registerViewFactory(
        _viewType,
        (int viewId) => video,
      );

      if (!mounted) {
        _stopStream(stream);
        return;
      }

      setState(() {
        _video = video;
        _stream = stream;
        _ready = true;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error =
            'Could not access the camera. Check browser permissions, '
            'or use Gallery to upload a photo.\n($e)';
      });
    }
  }

  void _stopStream(html.MediaStream? stream) {
    stream?.getTracks().forEach((t) => t.stop());
  }

  Future<void> _capture() async {
    final video = _video;
    if (video == null) return;

    final w = video.videoWidth;
    final h = video.videoHeight;
    if (w == 0 || h == 0) return;

    final canvas = html.CanvasElement(width: w, height: h);
    canvas.context2D.drawImageScaled(video, 0, 0, w, h);

    final dataUrl = canvas.toDataUrl('image/jpeg', 0.92);
    final bytes = base64Decode(dataUrl.split(',').last);
    final blob = html.Blob([Uint8List.fromList(bytes)], 'image/jpeg');
    final blobUrl = html.Url.createObjectUrlFromBlob(blob);

    _stopStream(_stream);
    if (mounted) Navigator.of(context).pop(blobUrl);
  }

  void _cancel() {
    _stopStream(_stream);
    Navigator.of(context).pop();
  }

  @override
  void dispose() {
    _stopStream(_stream);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppTheme.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560, maxHeight: 640),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Take a room photo',
                style: GoogleFonts.interTight(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.ink,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Allow camera access, then capture your space.',
                style: GoogleFonts.interTight(
                  fontSize: 13,
                  color: AppTheme.textMuted,
                ),
              ),
              const SizedBox(height: 16),
              ClipRRect(
                borderRadius: BorderRadius.circular(AppTheme.radiusMd),
                child: AspectRatio(
                  aspectRatio: 4 / 3,
                  child: ColoredBox(
                    color: AppTheme.ink,
                    child: _error != null
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(20),
                              child: Text(
                                _error!,
                                textAlign: TextAlign.center,
                                style: GoogleFonts.interTight(
                                  fontSize: 13,
                                  color: Colors.white,
                                  height: 1.45,
                                ),
                              ),
                            ),
                          )
                        : _ready
                            ? HtmlElementView(viewType: _viewType)
                            : const Center(
                                child: CircularProgressIndicator(
                                  color: AppTheme.primaryColor,
                                ),
                              ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _cancel,
                      child: const Text('Cancel'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _ready && _error == null ? _capture : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryColor,
                        foregroundColor: Colors.white,
                      ),
                      child: const Text('Capture'),
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
}
