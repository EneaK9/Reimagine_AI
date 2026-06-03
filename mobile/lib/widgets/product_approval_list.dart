import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/room_upgrade.dart';
import '../theme/app_theme.dart';
import 'shopping_card.dart';

class ProductApprovalList extends StatelessWidget {
  final List<SelectedProduct> selectedProducts;
  final double budget;
  final bool isGenerating;
  final ValueChanged<List<SelectedProduct>> onChanged;
  final VoidCallback onGenerate;

  const ProductApprovalList({
    super.key,
    required this.selectedProducts,
    required this.budget,
    required this.isGenerating,
    required this.onChanged,
    required this.onGenerate,
  });

  double get totalCost => selectedProducts.fold(
    0,
    (total, item) => total + item.chosenProduct.price,
  );

  @override
  Widget build(BuildContext context) {
    final overBudget = totalCost > budget;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Header(totalCost: totalCost, budget: budget, overBudget: overBudget),
        const SizedBox(height: 16),
        ...selectedProducts.asMap().entries.map((entry) {
          final index = entry.key;
          final selectedProduct = entry.value;
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Column(
              children: [
                ShoppingCard(selectedProduct: selectedProduct, compact: true),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerRight,
                  child: OutlinedButton.icon(
                    onPressed: selectedProduct.allCandidates.length <= 1
                        ? null
                        : () => _showSwapSheet(context, index, selectedProduct),
                    icon: const Icon(Icons.swap_horiz_rounded, size: 18),
                    label: const Text('Swap product'),
                  ),
                ),
              ],
            ),
          );
        }),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: isGenerating ? null : onGenerate,
            icon: isGenerating
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.auto_awesome_rounded),
            label: Text(
              isGenerating
                  ? 'Generating your upgrade...'
                  : 'Generate my upgrade',
            ),
          ),
        ),
      ],
    );
  }

  void _showSwapSheet(
    BuildContext context,
    int selectedIndex,
    SelectedProduct selectedProduct,
  ) {
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      backgroundColor: AppTheme.background,
      builder: (context) {
        return SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            children: [
              Text(
                'Choose another ${selectedProduct.shoppingListItem.itemName}',
                style: GoogleFonts.dmSans(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              ...selectedProduct.allCandidates.map((product) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _CandidateTile(
                    product: product,
                    isSelected:
                        product.buyLink ==
                        selectedProduct.chosenProduct.buyLink,
                    onTap: () {
                      final updated = [...selectedProducts];
                      updated[selectedIndex] = selectedProduct.copyWith(
                        chosenProduct: product,
                      );
                      onChanged(updated);
                      Navigator.pop(context);
                    },
                  ),
                );
              }),
            ],
          ),
        );
      },
    );
  }
}

class _Header extends StatelessWidget {
  final double totalCost;
  final double budget;
  final bool overBudget;

  const _Header({
    required this.totalCost,
    required this.budget,
    required this.overBudget,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: overBudget
            ? AppTheme.warning.withValues(alpha: 0.12)
            : AppTheme.primaryColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: overBudget
              ? AppTheme.warning.withValues(alpha: 0.5)
              : AppTheme.primaryColor.withValues(alpha: 0.2),
        ),
      ),
      child: Row(
        children: [
          Icon(
            overBudget
                ? Icons.warning_amber_rounded
                : Icons.shopping_bag_outlined,
            color: overBudget ? AppTheme.warning : AppTheme.primaryColor,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              overBudget
                  ? 'Best options found: \$${totalCost.toStringAsFixed(2)} over your \$${budget.toStringAsFixed(2)} budget.'
                  : 'Selected products total \$${totalCost.toStringAsFixed(2)} of your \$${budget.toStringAsFixed(2)} budget.',
              style: GoogleFonts.dmSans(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CandidateTile extends StatelessWidget {
  final Product product;
  final bool isSelected;
  final VoidCallback onTap;

  const _CandidateTile({
    required this.product,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? AppTheme.primaryColor : AppTheme.border,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: CachedNetworkImage(
                imageUrl: product.imageUrl,
                width: 58,
                height: 58,
                fit: BoxFit.cover,
                errorWidget: (_, _, _) => const Icon(Icons.chair_outlined),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    product.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.dmSans(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${product.store} • \$${product.price.toStringAsFixed(2)}',
                    style: GoogleFonts.dmSans(
                      fontSize: 12,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            if (isSelected)
              const Icon(
                Icons.check_circle_rounded,
                color: AppTheme.primaryColor,
              ),
          ],
        ),
      ),
    );
  }
}
