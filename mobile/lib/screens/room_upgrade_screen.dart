import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

import '../models/room_upgrade.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/before_after_view.dart';
import '../widgets/product_approval_list.dart';
import '../widgets/shopping_card.dart';

enum RoomUpgradeStatus {
  idle,
  analyzing,
  awaitingApproval,
  generating,
  done,
  error,
}

class RoomUpgradeScreen extends StatefulWidget {
  const RoomUpgradeScreen({super.key});

  @override
  State<RoomUpgradeScreen> createState() => _RoomUpgradeScreenState();
}

class _RoomUpgradeScreenState extends State<RoomUpgradeScreen> {
  final _apiService = ApiService();
  final _imagePicker = ImagePicker();
  final _promptController = TextEditingController(
    text: 'How can this look better with just \$100?',
  );
  final _budgetController = TextEditingController(text: '100');

  RoomUpgradeStatus _status = RoomUpgradeStatus.idle;
  XFile? _selectedImage;
  Uint8List? _selectedImageBytes;
  SceneAnalysis? _sceneAnalysis;
  List<SelectedProduct> _selectedProducts = [];
  String? _afterImageUrl;
  String? _errorMessage;

  @override
  void dispose() {
    _promptController.dispose();
    _budgetController.dispose();
    super.dispose();
  }

  bool get _isBusy =>
      _status == RoomUpgradeStatus.analyzing ||
      _status == RoomUpgradeStatus.generating;

  double get _budget => double.tryParse(_budgetController.text.trim()) ?? 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(title: const Text('Budget Room Upgrade')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildIntroCard(),
              const SizedBox(height: 18),
              _buildInputCard(),
              const SizedBox(height: 18),
              if (_status == RoomUpgradeStatus.analyzing)
                _buildLoadingCard(
                  'Analyzing your space and finding products...',
                ),
              if (_status == RoomUpgradeStatus.generating)
                _buildLoadingCard('Generating your upgraded space...'),
              if (_errorMessage != null) _buildErrorCard(),
              if (_sceneAnalysis != null &&
                  _selectedProducts.isNotEmpty &&
                  _afterImageUrl == null)
                ProductApprovalList(
                  selectedProducts: _selectedProducts,
                  budget: _budget,
                  isGenerating: _status == RoomUpgradeStatus.generating,
                  onChanged: (products) => setState(() {
                    _selectedProducts = products;
                  }),
                  onGenerate: _generateUpgrade,
                ),
              if (_afterImageUrl != null && _selectedImageBytes != null)
                _buildResults(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildIntroCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.auto_awesome_rounded, color: Colors.white),
          const SizedBox(height: 14),
          Text(
            'Upgrade any room or yard on a real budget',
            style: GoogleFonts.dmSerifDisplay(
              fontSize: 30,
              color: Colors.white,
              height: 1.05,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Upload a photo, set a budget, approve real products, then preview the final look.',
            style: GoogleFonts.dmSans(
              fontSize: 14,
              color: Colors.white.withValues(alpha: 0.92),
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputCard() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppTheme.border),
        boxShadow: AppTheme.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '1. Start with your photo',
            style: GoogleFonts.dmSans(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          InkWell(
            onTap: _isBusy ? null : _pickImage,
            borderRadius: BorderRadius.circular(18),
            child: Container(
              height: 180,
              width: double.infinity,
              decoration: BoxDecoration(
                color: AppTheme.inputBackground,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: AppTheme.border),
              ),
              clipBehavior: Clip.antiAlias,
              child: _selectedImageBytes == null
                  ? const Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.add_photo_alternate_outlined,
                          color: AppTheme.primaryColor,
                          size: 36,
                        ),
                        SizedBox(height: 8),
                        Text('Tap to choose a room or yard photo'),
                      ],
                    )
                  : Image.memory(_selectedImageBytes!, fit: BoxFit.cover),
            ),
          ),
          const SizedBox(height: 18),
          TextField(
            controller: _promptController,
            minLines: 2,
            maxLines: 4,
            enabled: !_isBusy,
            decoration: const InputDecoration(
              labelText: 'What do you want?',
              hintText: 'Make this room look better for \$100',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _budgetController,
            enabled: !_isBusy,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Budget',
              prefixText: '\$',
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _isBusy ? null : _analyzeUpgrade,
              icon: const Icon(Icons.search_rounded),
              label: const Text('Find products under budget'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingCard(String message) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.border),
      ),
      child: Row(
        children: [
          const CircularProgressIndicator(),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              message,
              style: GoogleFonts.dmSans(
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorCard() {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.error.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
      ),
      child: Text(
        _errorMessage!,
        style: GoogleFonts.dmSans(color: AppTheme.textPrimary),
      ),
    );
  }

  Widget _buildResults() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        BeforeAfterView(
          beforeImageBytes: _selectedImageBytes!,
          afterImageUrl: _afterImageUrl!,
        ),
        const SizedBox(height: 18),
        Text(
          'Shop this look',
          style: GoogleFonts.dmSans(
            fontSize: 18,
            fontWeight: FontWeight.w800,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 10),
        ..._selectedProducts.map(
          (product) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: ShoppingCard(selectedProduct: product),
          ),
        ),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: _status == RoomUpgradeStatus.generating
                ? null
                : _generateUpgrade,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Regenerate preview'),
          ),
        ),
      ],
    );
  }

  Future<void> _pickImage() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Choose from gallery'),
              onTap: () => Navigator.pop(context, ImageSource.gallery),
            ),
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Take a photo'),
              onTap: () => Navigator.pop(context, ImageSource.camera),
            ),
          ],
        ),
      ),
    );
    if (source == null) return;

    final image = await _imagePicker.pickImage(
      source: source,
      imageQuality: 88,
      maxWidth: 1600,
    );
    if (image == null) return;

    final bytes = await image.readAsBytes();
    setState(() {
      _selectedImage = image;
      _selectedImageBytes = bytes;
      _sceneAnalysis = null;
      _selectedProducts = [];
      _afterImageUrl = null;
      _errorMessage = null;
      _status = RoomUpgradeStatus.idle;
    });
  }

  Future<void> _analyzeUpgrade() async {
    final image = _selectedImage;
    if (image == null) {
      _setError('Please choose a photo first.');
      return;
    }
    if (_budget <= 0) {
      _setError('Please enter a valid budget.');
      return;
    }

    setState(() {
      _status = RoomUpgradeStatus.analyzing;
      _errorMessage = null;
      _afterImageUrl = null;
    });

    try {
      final result = await _apiService.analyzeRoomUpgrade(
        imageFile: image,
        prompt: _promptController.text.trim(),
        budget: _budget,
      );
      setState(() {
        _sceneAnalysis = result.sceneAnalysis;
        _selectedProducts = result.selectedProducts;
        _status = RoomUpgradeStatus.awaitingApproval;
      });
      if (result.selectedProducts.isEmpty) {
        _setError(
          'No products were found. Try a larger budget or simpler request.',
        );
      }
    } catch (e) {
      _setError(e.toString());
    }
  }

  Future<void> _generateUpgrade() async {
    final image = _selectedImage;
    final analysis = _sceneAnalysis;
    if (image == null || analysis == null || _selectedProducts.isEmpty) {
      _setError('Approve at least one product before generating.');
      return;
    }

    setState(() {
      _status = RoomUpgradeStatus.generating;
      _errorMessage = null;
    });

    try {
      final result = await _apiService.generateUpgradeImage(
        imageFile: image,
        prompt: _promptController.text.trim(),
        sceneAnalysis: analysis,
        selectedProducts: _selectedProducts,
      );
      setState(() {
        _afterImageUrl = result.afterImageUrl;
        _status = RoomUpgradeStatus.done;
      });
      if (result.afterImageUrl == null) {
        _setError('Image generation did not return a preview. Try again.');
      }
    } catch (e) {
      _setError(e.toString());
    }
  }

  void _setError(String message) {
    setState(() {
      _errorMessage = message;
      _status = RoomUpgradeStatus.error;
    });
  }
}
