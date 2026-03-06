def apply_table_scrollbar_style(table):
    table.setStyleSheet(table.styleSheet() + """
        /* ===== Scrollbar Vertical ===== */
        QScrollBar:vertical {
            background: rgba(255,255,255,20);
            width: 10px;
            border-radius: 5px;
            margin: 2px;
        }

        QScrollBar::handle:vertical {
            background: rgba(255,255,255,80);
            border-radius: 5px;
            min-height: 30px;
        }

        QScrollBar::handle:vertical:hover {
            background: rgba(255,255,255,140);
        }

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            background: none;
            border: none;
        }

        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {
            background: none;
        }

        /* ===== Scrollbar Horizontal ===== */
        QScrollBar:horizontal {
            background: rgba(255,255,255,20);
            height: 10px;
            border-radius: 5px;
            margin: 2px;
        }

        QScrollBar::handle:horizontal {
            background: rgba(255,255,255,80);
            border-radius: 5px;
            min-width: 30px;
        }

        QScrollBar::handle:horizontal:hover {
            background: rgba(255,255,255,140);
        }

        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            background: none;
            border: none;
        }

        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {
            background: none;
        }
    """)