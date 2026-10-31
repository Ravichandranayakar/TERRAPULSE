import matplotlib.pyplot as plt
import numpy as np
import os

# Set style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig = plt.figure(figsize=(16, 10), dpi=300)
fig.patch.set_facecolor('#0f172a') # Slate-900

# Color palette
PRIMARY = '#06b6d4'   # Cyan (LightGBM - Active)
SECONDARY = '#3b82f6' # Blue (XGBoost)
ACCENT = '#f59e0b'    # Amber (Random Forest)
MUTED = '#94a3b8'     # Slate-400 (Logistic Regression)

models = ['Logistic Reg\n(Baseline)', 'Random Forest\n(v0.2)', 'XGBoost\n(Benchmark)', 'LightGBM\n(v0.4 - Active)']
x = np.arange(len(models))

# 1. Main CV Metrics Comparison
ax1 = plt.subplot(2, 2, 1)
ax1.set_facecolor('#1e293b')
f1_scores = [0.6937, 0.7070, 0.7186, 0.7200]
roc_auc = [0.6689, 0.7354, 0.7424, 0.7389]
recalls = [0.9028, 0.8319, 0.8752, 0.8854]

width = 0.25
rects1 = ax1.bar(x - width, f1_scores, width, label='F1-Score (Primary)', color='#10b981')
rects2 = ax1.bar(x, roc_auc, width, label='ROC-AUC (Ranking)', color=PRIMARY)
rects3 = ax1.bar(x + width, recalls, width, label='Recall (Catch Rate)', color=ACCENT)

ax1.set_title('Spatial Block Cross-Validation (5 Folds)', fontsize=14, fontweight='bold', color='white', pad=12)
ax1.set_xticks(x)
ax1.set_xticklabels(models, color='white', fontsize=10)
ax1.set_ylim(0.5, 1.0)
ax1.tick_params(colors='white')
ax1.legend(loc='upper left', facecolor='#0f172a', edgecolor='#334155', labelcolor='white', fontsize=9)
ax1.grid(color='#334155', linestyle='--', alpha=0.5)

for rects in [rects1, rects2, rects3]:
    for rect in rects:
        h = rect.get_height()
        ax1.annotate(f'{h:.2f}',
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', color='white', fontsize=8, fontweight='bold')

# 2. Held-Out Unseen State Recall (The Life-Saving Metric)
ax2 = plt.subplot(2, 2, 2)
ax2.set_facecolor('#1e293b')
unseen_recall = [83.61, 71.86, 68.69, 82.11]
colors = [MUTED, ACCENT, SECONDARY, '#10b981']

bars2 = ax2.bar(models, unseen_recall, color=colors, width=0.55, edgecolor='#334155')
ax2.set_title('Unseen State Recall (% Landslides Caught on New Terrain)', fontsize=14, fontweight='bold', color='white', pad=12)
ax2.set_ylim(50, 100)
ax2.tick_params(colors='white')
ax2.grid(color='#334155', linestyle='--', alpha=0.5)

for bar in bars2:
    y = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2, y + 1.2, f'{y:.1f}%', ha='center', va='bottom', color='white', fontweight='bold', fontsize=11)

ax2.axhline(80, color='#10b981', linestyle=':', alpha=0.7, label='Safety Standard (80%)')
ax2.legend(loc='lower right', facecolor='#0f172a', edgecolor='#334155', labelcolor='white')

# 3. Model Footprint & Edge Deployment Size
ax3 = plt.subplot(2, 2, 3)
ax3.set_facecolor('#1e293b')
sizes = [0.05, 13.9, 2.1, 2.1] # MB
bars3 = ax3.bar(models, sizes, color=[MUTED, '#ef4444', SECONDARY, '#10b981'], width=0.55)
ax3.set_title('Artifact Footprint (MB) — Offline & Edge Readiness', fontsize=14, fontweight='bold', color='white', pad=12)
ax3.set_ylabel('Size (MB)', color='white')
ax3.tick_params(colors='white')
ax3.grid(color='#334155', linestyle='--', alpha=0.5)

for bar in bars3:
    y = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2, y + 0.3, f'{y:.1f} MB', ha='center', va='bottom', color='white', fontweight='bold', fontsize=10)

ax3.text(1, 11.5, '6.7x Larger\n(High RAM)', color='#fca5a5', ha='center', fontsize=9, fontweight='bold')
ax3.text(3, 4.0, '6.7x Smaller\n(Edge-Ready)', color='#86efac', ha='center', fontsize=9, fontweight='bold')

# 4. Impact of ISRO/NRSC Bhuvan Geology Layer (Dataset v0.1 vs v0.2)
ax4 = plt.subplot(2, 2, 4)
ax4.set_facecolor('#1e293b')
models_feat = ['Random Forest', 'XGBoost', 'LightGBM']
f1_v1 = [0.7170, 0.7165, 0.7152]
f1_v2 = [0.7070, 0.7186, 0.7200]

x_feat = np.arange(len(models_feat))
w = 0.35
rects_v1 = ax4.bar(x_feat - w/2, f1_v1, w, label='Dataset v0.1 (Baseline)', color='#64748b')
rects_v2 = ax4.bar(x_feat + w/2, f1_v2, w, label='Dataset v0.2 (+ Bhuvan Geology)', color='#06b6d4')

ax4.set_title('Impact of Adding Bhuvan Geology & Lineaments (F1-Score)', fontsize=14, fontweight='bold', color='white', pad=12)
ax4.set_xticks(x_feat)
ax4.set_xticklabels(models_feat, color='white', fontsize=10)
ax4.set_ylim(0.68, 0.74)
ax4.tick_params(colors='white')
ax4.legend(loc='lower left', facecolor='#0f172a', edgecolor='#334155', labelcolor='white', fontsize=9)
ax4.grid(color='#334155', linestyle='--', alpha=0.5)

for rect in rects_v1 + rects_v2:
    h = rect.get_height()
    ax4.annotate(f'{h:.4f}',
                xy=(rect.get_x() + rect.get_width() / 2, h),
                xytext=(0, 2), textcoords="offset points",
                ha='center', va='bottom', color='white', fontsize=8)

plt.suptitle('TerraPulse.ai — ML Model Benchmark & Selection Architecture\nEvaluated on 17,092 GSI Real Points across 8 North-Eastern States', 
             fontsize=17, fontweight='bold', color='white', y=0.98)

plt.tight_layout(rect=[0, 0.03, 1, 0.94])
output_path = os.path.join(os.getcwd(), 'TERRAPULSE_MODEL_COMPARISON_CHART.png')
plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
print(f"Successfully generated comparison chart at: {output_path}")

