import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../models/room_upgrade.dart';
import '../theme/app_theme.dart';

class DesignAdviceCard extends StatelessWidget {
  final YardDesignAdvice advice;

  const DesignAdviceCard({super.key, required this.advice});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
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
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppTheme.primaryColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.yard_rounded,
                  color: AppTheme.primaryColor,
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Designer Advice',
                      style: GoogleFonts.dmSans(
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      'What to do before you buy or generate',
                      style: GoogleFonts.dmSans(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (advice.spaceAssessment != null)
            _SummarySection(assessment: advice.spaceAssessment!),
          if (advice.designApproach != null)
            _ApproachSection(approach: advice.designApproach!),
          if (advice.warnings.isNotEmpty)
            _WarningsSection(warnings: advice.warnings),
          if (advice.keyConstraints.isNotEmpty)
            _ConstraintsSection(constraints: advice.keyConstraints),
          if (advice.actionPlan.isNotEmpty)
            _ActionPlanSection(steps: advice.actionPlan),
          if (advice.productRequirements.isNotEmpty)
            _ProductRequirementsSection(
              requirements: advice.productRequirements,
            ),
          if (advice.seasonalNotes != null)
            _SeasonalNotesSection(notes: advice.seasonalNotes!),
        ],
      ),
    );
  }
}

class _SummarySection extends StatelessWidget {
  final SpaceAssessment assessment;

  const _SummarySection({required this.assessment});

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Space Assessment',
      icon: Icons.visibility_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            assessment.summary,
            style: GoogleFonts.dmSans(
              fontSize: 14,
              height: 1.4,
              color: AppTheme.textPrimary,
            ),
          ),
          if (assessment.keyCharacteristics.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: assessment.keyCharacteristics
                  .map((item) => _SmallChip(label: item))
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }
}

class _ApproachSection extends StatelessWidget {
  final DesignApproach approach;

  const _ApproachSection({required this.approach});

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Design Approach',
      icon: Icons.auto_awesome_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _TextBlock(title: approach.strategy, body: approach.reasoning),
          if (approach.focalPoint != null &&
              approach.focalPoint!.trim().isNotEmpty) ...[
            const SizedBox(height: 10),
            _InlineDetail(label: 'Focal point', value: approach.focalPoint!),
          ],
          if (approach.zones.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: approach.zones
                  .map((zone) => _SmallChip(label: zone))
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }
}

class _WarningsSection extends StatelessWidget {
  final List<DesignWarning> warnings;

  const _WarningsSection({required this.warnings});

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Warnings',
      icon: Icons.warning_amber_rounded,
      child: Column(
        children: warnings.map((warning) {
          final color = _warningColor(warning);
          return Container(
            width: double.infinity,
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: color.withValues(alpha: 0.25)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(_warningIcon(warning), color: color, size: 18),
                const SizedBox(width: 10),
                Expanded(
                  child: _TextBlock(
                    title: warning.title,
                    body: warning.message,
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Color _warningColor(DesignWarning warning) {
    if (warning.isCritical) return AppTheme.error;
    if (warning.isImportant) return AppTheme.warning;
    return AppTheme.primaryColor;
  }

  IconData _warningIcon(DesignWarning warning) {
    if (warning.isCritical) return Icons.error_outline_rounded;
    if (warning.isImportant) return Icons.priority_high_rounded;
    return Icons.info_outline_rounded;
  }
}

class _ConstraintsSection extends StatelessWidget {
  final List<DesignConstraint> constraints;

  const _ConstraintsSection({required this.constraints});

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Key Constraints',
      icon: Icons.rule_rounded,
      child: Column(
        children: constraints.map((constraint) {
          return Container(
            margin: const EdgeInsets.only(bottom: 10),
            decoration: BoxDecoration(
              color: AppTheme.inputBackground,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppTheme.border),
            ),
            child: ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(horizontal: 14),
              childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
              title: Text(
                constraint.title,
                style: GoogleFonts.dmSans(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary,
                ),
              ),
              children: [
                _TextBlock(
                  title: 'Why it matters',
                  body: constraint.explanation,
                ),
                const SizedBox(height: 10),
                _TextBlock(title: 'Impact', body: constraint.impact),
                const SizedBox(height: 10),
                _TextBlock(title: 'Your action', body: constraint.userAction),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _ActionPlanSection extends StatelessWidget {
  final List<ActionStep> steps;

  const _ActionPlanSection({required this.steps});

  @override
  Widget build(BuildContext context) {
    final sortedSteps = [...steps]..sort((a, b) => a.step.compareTo(b.step));
    return _Section(
      title: 'Action Plan',
      icon: Icons.format_list_numbered_rounded,
      child: Column(
        children: sortedSteps.map((step) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 28,
                  height: 28,
                  alignment: Alignment.center,
                  decoration: const BoxDecoration(
                    color: AppTheme.primaryColor,
                    shape: BoxShape.circle,
                  ),
                  child: Text(
                    '${step.step}',
                    style: GoogleFonts.dmSans(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _TextBlock(
                    title: step.action,
                    body: '${step.detail}\n\n${step.reasoning}',
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _ProductRequirementsSection extends StatelessWidget {
  final List<ProductRequirement> requirements;

  const _ProductRequirementsSection({required this.requirements});

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'Product Requirements',
      icon: Icons.shopping_bag_outlined,
      child: Column(
        children: requirements.map((requirement) {
          return Container(
            width: double.infinity,
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.inputBackground,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _TextBlock(
                  title: requirement.category,
                  body: requirement.requirements,
                ),
                if (requirement.placement.trim().isNotEmpty) ...[
                  const SizedBox(height: 8),
                  _InlineDetail(
                    label: 'Placement',
                    value: requirement.placement,
                  ),
                ],
                if (requirement.searchTerms.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: requirement.searchTerms
                        .map((term) => _SmallChip(label: term))
                        .toList(),
                  ),
                ],
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _SeasonalNotesSection extends StatelessWidget {
  final SeasonalNotes notes;

  const _SeasonalNotesSection({required this.notes});

  @override
  Widget build(BuildContext context) {
    final items = <String, String?>{
      'Spring': notes.spring,
      'Summer': notes.summer,
      'Autumn': notes.autumn,
      'Winter': notes.winter,
    }.entries.where((entry) => entry.value?.trim().isNotEmpty ?? false);

    if (items.isEmpty) return const SizedBox.shrink();

    return _Section(
      title: 'Seasonal Notes',
      icon: Icons.calendar_month_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: items
            .map(
              (entry) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _InlineDetail(label: entry.key, value: entry.value!),
              ),
            )
            .toList(),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;

  const _Section({
    required this.title,
    required this.icon,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: AppTheme.primaryColor),
              const SizedBox(width: 8),
              Text(
                title,
                style: GoogleFonts.dmSans(
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          child,
        ],
      ),
    );
  }
}

class _TextBlock extends StatelessWidget {
  final String title;
  final String body;

  const _TextBlock({required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: GoogleFonts.dmSans(
            fontSize: 13,
            fontWeight: FontWeight.w800,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          body,
          style: GoogleFonts.dmSans(
            fontSize: 13,
            height: 1.45,
            color: AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }
}

class _InlineDetail extends StatelessWidget {
  final String label;
  final String value;

  const _InlineDetail({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return RichText(
      text: TextSpan(
        style: GoogleFonts.dmSans(
          fontSize: 13,
          height: 1.45,
          color: AppTheme.textSecondary,
        ),
        children: [
          TextSpan(
            text: '$label: ',
            style: const TextStyle(
              fontWeight: FontWeight.w800,
              color: AppTheme.textPrimary,
            ),
          ),
          TextSpan(text: value),
        ],
      ),
    );
  }
}

class _SmallChip extends StatelessWidget {
  final String label;

  const _SmallChip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.primaryColor.withValues(alpha: 0.18)),
      ),
      child: Text(
        label,
        style: GoogleFonts.dmSans(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: AppTheme.primaryDark,
        ),
      ),
    );
  }
}
