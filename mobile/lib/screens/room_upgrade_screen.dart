import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

import '../models/room_upgrade.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/before_after_view.dart';
import '../widgets/design_advice_card.dart';
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
  final _dimensionsController = TextEditingController();
  final _cityController = TextEditingController();

  RoomUpgradeStatus _status = RoomUpgradeStatus.idle;
  XFile? _selectedImage;
  Uint8List? _selectedImageBytes;
  SceneAnalysis? _sceneAnalysis;
  List<SelectedProduct> _selectedProducts = [];
  String? _afterImageUrl;
  String? _errorMessage;
  YardDesignAdvice? _designAdvice;
  bool _showAdvancedOptions = false;

  // Yard design inputs
  String? _orientation;
  String? _surfaceType;
  String? _slope;
  String? _environmentType;
  String? _primaryPurpose;
  final List<String> _whoUses = [];
  String? _maintenance;
  String? _stylePreference;
  String? _ownership;

  @override
  void dispose() {
    _promptController.dispose();
    _budgetController.dispose();
    _dimensionsController.dispose();
    _cityController.dispose();
    super.dispose();
  }

  bool get _isBusy =>
      _status == RoomUpgradeStatus.analyzing ||
      _status == RoomUpgradeStatus.generating;

  double get _budget => double.tryParse(_budgetController.text.trim()) ?? 0;

  YardDesignInputs get _yardInputs => YardDesignInputs(
        dimensionsSqm: double.tryParse(_dimensionsController.text.trim()),
        orientation: _orientation,
        surfaceType: _surfaceType,
        slope: _slope,
        cityOrRegion: _emptyToNull(_cityController.text),
        environmentType: _environmentType,
        primaryPurpose: _primaryPurpose,
        whoUses: _whoUses.isEmpty ? null : _whoUses,
        maintenance: _maintenance,
        stylePreference: _stylePreference,
        ownership: _ownership,
      );

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
              if (_designAdvice != null && !_designAdvice!.isEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 18),
                  child: DesignAdviceCard(advice: _designAdvice!),
                ),
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
              labelText: 'What do you want? (optional)',
              hintText: 'Optional: make this yard better for summer evenings',
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
          _buildAdvancedOptionsSection(),
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

  Widget _buildAdvancedOptionsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => setState(() => _showAdvancedOptions = !_showAdvancedOptions),
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(
              children: [
                Icon(
                  _showAdvancedOptions
                      ? Icons.keyboard_arrow_up_rounded
                      : Icons.keyboard_arrow_down_rounded,
                  color: AppTheme.primaryColor,
                  size: 20,
                ),
                const SizedBox(width: 6),
                Text(
                  'Advanced Options',
                  style: GoogleFonts.dmSans(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.primaryColor,
                  ),
                ),
                const Spacer(),
                Text(
                  'Optional - for smarter recommendations',
                  style: GoogleFonts.dmSans(
                    fontSize: 11,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ),
        if (_showAdvancedOptions) ...[
          const SizedBox(height: 12),
          _buildAdvancedOptions(),
        ],
      ],
    );
  }

  Widget _buildAdvancedOptions() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.inputBackground,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.border.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Row 1: Dimensions & City
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _dimensionsController,
                  enabled: !_isBusy,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Size (m²)',
                    hintText: 'e.g. 25',
                    isDense: true,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _cityController,
                  enabled: !_isBusy,
                  decoration: const InputDecoration(
                    labelText: 'City/Region',
                    hintText: 'e.g. Miami',
                    isDense: true,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Row 2: Orientation & Surface
          Row(
            children: [
              Expanded(
                child: _buildDropdown(
                  label: 'Orientation',
                  value: _orientation,
                  items: const ['north', 'south', 'east', 'west'],
                  onChanged: (v) => setState(() => _orientation = v),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildDropdown(
                  label: 'Surface',
                  value: _surfaceType,
                  items: const ['grass', 'concrete', 'gravel', 'decking', 'bare_soil', 'mixed'],
                  onChanged: (v) => setState(() => _surfaceType = v),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Row 3: Environment & Purpose
          Row(
            children: [
              Expanded(
                child: _buildDropdown(
                  label: 'Environment',
                  value: _environmentType,
                  items: const ['coastal', 'suburban', 'urban', 'rural', 'mountain'],
                  onChanged: (v) => setState(() => _environmentType = v),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildDropdown(
                  label: 'Main Purpose',
                  value: _primaryPurpose,
                  items: const ['dining', 'relaxing', 'children_play', 'food_growing', 'aesthetic'],
                  onChanged: (v) => setState(() => _primaryPurpose = v),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Row 4: Slope & Maintenance
          Row(
            children: [
              Expanded(
                child: _buildDropdown(
                  label: 'Slope',
                  value: _slope,
                  items: const ['flat', 'gentle', 'significant'],
                  onChanged: (v) => setState(() => _slope = v),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildDropdown(
                  label: 'Maintenance',
                  value: _maintenance,
                  items: const ['low', 'medium', 'high'],
                  onChanged: (v) => setState(() => _maintenance = v),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Row 5: Style & Ownership
          Row(
            children: [
              Expanded(
                child: _buildDropdown(
                  label: 'Style',
                  value: _stylePreference,
                  items: const ['modern', 'rustic', 'coastal', 'tropical', 'mediterranean', 'scandinavian', 'industrial'],
                  onChanged: (v) => setState(() => _stylePreference = v),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildDropdown(
                  label: 'Ownership',
                  value: _ownership,
                  items: const ['owner', 'renter'],
                  onChanged: (v) => setState(() => _ownership = v),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Who uses this space (multi-select chips)
          Text(
            'Who uses this space?',
            style: GoogleFonts.dmSans(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: ['adults', 'children', 'dogs', 'cats', 'elderly', 'entertaining'].map((user) {
              final isSelected = _whoUses.contains(user);
              return FilterChip(
                label: Text(_formatLabel(user)),
                selected: isSelected,
                onSelected: _isBusy
                    ? null
                    : (selected) {
                        setState(() {
                          if (selected) {
                            _whoUses.add(user);
                          } else {
                            _whoUses.remove(user);
                          }
                        });
                      },
                selectedColor: AppTheme.primaryColor.withValues(alpha: 0.2),
                checkmarkColor: AppTheme.primaryColor,
                labelStyle: GoogleFonts.dmSans(
                  fontSize: 12,
                  color: isSelected ? AppTheme.primaryColor : AppTheme.textSecondary,
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildDropdown({
    required String label,
    required String? value,
    required List<String> items,
    required ValueChanged<String?> onChanged,
  }) {
    return DropdownButtonFormField<String>(
      initialValue: value,
      decoration: InputDecoration(
        labelText: label,
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      ),
      items: [
        const DropdownMenuItem<String>(value: null, child: Text('—')),
        ...items.map((item) => DropdownMenuItem(
              value: item,
              child: Text(_formatLabel(item)),
            )),
      ],
      onChanged: _isBusy ? null : onChanged,
      style: GoogleFonts.dmSans(fontSize: 13, color: AppTheme.textPrimary),
      isExpanded: true,
    );
  }

  String _formatLabel(String value) {
    return value.replaceAll('_', ' ').split(' ').map((word) {
      if (word.isEmpty) return word;
      return word[0].toUpperCase() + word.substring(1);
    }).join(' ');
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
      _designAdvice = null;
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
      _designAdvice = null;
    });

    try {
      final yardInputs = _yardInputs;
      final result = await _apiService.analyzeRoomUpgrade(
        imageFile: image,
        prompt: _promptController.text.trim(),
        budget: _budget,
        yardInputs: yardInputs.hasInputs ? yardInputs : null,
      );
      setState(() {
        _sceneAnalysis = result.sceneAnalysis;
        _selectedProducts = result.selectedProducts;
        _designAdvice = result.designAdvice;
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

  String? _emptyToNull(String value) {
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
}
