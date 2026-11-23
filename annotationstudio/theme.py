"""A restrained, warm palette; category hue and review brightness are independent."""
from PySide6.QtGui import QColor

PALETTE = {
    'Activity Episode': '#75628C',
    'Motion Primitive': '#A85337', 'Body Posture': '#967633',
    'Hand Behavior': '#5B7959', 'Locomotion': '#B0773A',
    'Gesture': '#A34532', 'Action / HOI': '#82663A', 'HOI': '#82663A',
    'Facial Expression': '#71845A', 'Emotion': '#AE724C', 'Affect': '#AE724C',
    'Gaze / Attention': '#50786A', 'Speaking': '#987435',
    'Vocal Event': '#AD503C', 'Audio Activity': '#887861',
    'Speech / Dialogue': '#987435', 'Social Interaction': '#716D46',
    'QC / Notes': '#77746E',
    'Gesture Type': '#A34532', 'Gesture Phase': '#B1783D',
    'Speech-Gesture Relation': '#7E7950', 'Perceived Affect': '#AE724C',
    'Dialogue Event': '#987435', 'Proxemic Movement': '#8E633A',
    'Spatial Configuration': '#737D4F', 'Activity Relation': '#6E795C',
    'Object Spatial Relation': '#64785F', 'Object-relative Movement': '#A16443',
    'Interaction Event': '#A24D36',
    'Speech Turn': '#9B6C31', 'Turn Transition': '#B15A37',
    'Speech Timing': '#77805A',
    'Whole-body Action': '#9B563B', 'Gait Pattern': '#7B7D47',
    'Physical Interaction': '#964B2E', 'Cognitive State Expression': '#6A7956',
    'Speech Disfluency': '#9D7A43',
}

def category_color(category, status='pending', editing=False, override=''):
    base = QColor(override or PALETTE.get(category, '#8C7354'))
    if not base.isValid(): base = QColor('#8C7354')
    if status == 'rejected' and not editing: return QColor('#D6D1C9')
    white = .32 if editing else (.73 if status == 'approved' else 0.)
    dark = .0 if editing or status == 'approved' else .18
    return QColor(*[round(v * (1-white) * (1-dark) + 255*white)
                    for v in (base.red(), base.green(), base.blue())])

STYLE = '''
QWidget { font-family: "Segoe UI", "Inter", "DejaVu Sans", Arial; font-size: 9pt; color: #352E29; }
QMainWindow, QWidget#Root { background: #F4F2ED; }
QWidget#TopBar { background: #2D2723; }
QWidget#TopBar QLabel { color: #F7F2E8; }
QLabel#Brand { font-size: 17pt; font-weight: 700; }
QLabel#Monogram { background: #AE4E32; color: #FFF7ED; border-radius: 8px; font-size: 11pt; font-weight: 800; }
QLabel#Subtitle { color: #BFB4A6; font-size: 8pt; }
QLabel#Subhead { color: #847366; font-size: 8pt; font-weight: 700; }
QLabel#WorkspaceTitle { color: #352B25; font-size: 13pt; font-weight: 700; }
QLabel#TimeCode { font-family: "Consolas", "DejaVu Sans Mono"; font-size: 15pt; font-weight: 600; color: #A74B31; }
QFrame#Card, QFrame#TimelinePane, QFrame#SegmentEditor { background: #FFFFFF; border: 1px solid #E0DAD0; border-radius: 8px; }
QFrame#SegmentEditor[active="true"] { border: 1px solid #B15B3E; background: #FFFDF9; }
QPushButton { color: #514338; background: #FBFAF7; border: 1px solid #DCD5C9; border-radius: 5px; padding: 6px 10px; }
QPushButton:hover { border-color: #AE6749; background: #F6EFE5; }
QPushButton:pressed { background: #EBD9C8; }
QPushButton:disabled { color: #A59D91; background: #F3F0EA; border-color: #E8E2D7; }
QPushButton#PrimaryButton { background: #A94E32; color: #FFFFFF; border-color: #A94E32; font-weight: 650; }
QPushButton#PrimaryButton:hover { background: #913C26; }
QPushButton#PrimaryButton:disabled { background: #C8AB9B; color: #FAF5EF; border-color: #C8AB9B; }
QPushButton#TopButton { background: #3C342E; color: #EEE5D9; border-color: #67574A; }
QPushButton#TopAccent { background: #BD5B39; color: #FFFFFF; border-color: #BD5B39; font-weight: 700; }
QPushButton#Nav { background: transparent; border: none; border-radius: 0; padding: 11px 12px; color: #756759; }
QPushButton#Nav:checked { color: #9D432C; border-bottom: 3px solid #AA4F32; font-weight: 700; background: #F8EEE4; }
QPushButton#Chip { padding: 5px 9px; border-radius: 5px; background: #FAF7F0; }
QPushButton#Chip:checked { background: #ECD9C5; border-color: #C29677; color: #783A27; }
QLineEdit,QComboBox,QDoubleSpinBox,QSpinBox,QPlainTextEdit { background: #FFFFFF; border: 1px solid #DAD3C8; border-radius: 4px; padding: 5px 7px; selection-background-color: #ECD1BD; selection-color: #332921; }
QLineEdit:focus,QComboBox:focus,QDoubleSpinBox:focus,QPlainTextEdit:focus { border-color: #A95334; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: white; color: #42342C; selection-background-color: #F1DCCB; }
QTreeWidget,QTableWidget,QListWidget { background: #FFFFFF; alternate-background-color: #FAF8F3; border: 1px solid #E6DFD4; border-radius: 5px; }
QTreeWidget::item,QTableWidget::item,QListWidget::item { padding: 5px; }
QTreeWidget::item:selected,QTableWidget::item:selected,QListWidget::item:selected { background: #EFE0CF; color: #5E3827; }
QHeaderView::section { background: #F3EFE7; border: none; border-bottom: 1px solid #E4DDD2; padding: 6px; color: #7A6A5B; font-weight: 600; }
QTabWidget::pane { border: 1px solid #E0D8CC; background: #FFFFFF; border-radius: 5px; }
QTabBar::tab { background: #F0EBE2; padding: 8px 11px; }
QTabBar::tab:selected { background: #FFFDF8; color: #93462E; border-top: 2px solid #A85337; }
QSplitter::handle { background: #E4DDD2; width: 4px; height: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #F2EEE6; width: 10px; }
QScrollBar::handle:vertical { background: #C6B9A7; min-height: 25px; border-radius: 4px; }
QScrollBar:horizontal { background: #F2EEE6; height: 10px; }
QScrollBar::handle:horizontal { background: #C6B9A7; min-width: 25px; border-radius: 4px; }
QScrollBar::add-line,QScrollBar::sub-line { width: 0; height: 0; }
QCheckBox { spacing: 5px; }
QStatusBar { background: #ECE6DC; color: #766454; }
QSlider::groove:horizontal { height: 4px; background: #DED4C6; border-radius: 2px; }
QSlider::handle:horizontal { background: #AB5335; width: 12px; margin: -5px 0; border-radius: 6px; }
QDockWidget::title { background: #EFE9DF; padding: 6px 9px; color: #746151; }
QGroupBox { border: 1px solid #E6DFD4; border-radius: 5px; margin-top: 12px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #866E5A; }
QToolTip { color: #FFF9ED; background: #493A2F; border: 1px solid #79614D; padding: 6px; }
QMenuBar { background: #F1ECE3; color: #75604F; }
QMenu { background: #FFFCF7; border: 1px solid #DCCCB9; }
QMenu::item:selected { background: #EEDAC7; }
'''
