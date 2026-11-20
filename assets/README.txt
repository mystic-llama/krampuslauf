KRAMPUSLAUF ARTWORK

logo.png              350 x 350 source and Checklist display size.
banner_logo.png       Stacked presents; two 74 x 74 images flank the centered title.
title_banner.png      Supplied title art, shown through a padding-free header viewport.
helplogo.png          350 x 350 source; Help shows it at 176 x 176 beside the project links.
paypal_donate.png     PayPal donate button and card marks. Help opens the hosted donation page when it is clicked.
discord.png           Discord mark shown beside @mystikllama for in-game gold.
Krampuslauf.ico    Window icon and PyInstaller EXE icon.

Ordinary files; no base64 or encoded image strings. The transparent ICO is used for the window and EXE build.
Windows scales their display with DPI.

screen_markers/       Built-in Classic Client menu markers (static game artwork,
                      captured at 100% scaling). Required for automation; their
                      positions are defined in menu_layout.py. Do not replace
                      them with crops containing account or character names.

Replace the PNG files in this assets folder beside the EXE, then restart.
A missing or unreadable image leaves its reserved area empty and does not stop
startup. Rebuild the EXE to change its embedded icon.
