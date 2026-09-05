path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\LandslideMap.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

import re

# Fix the missing </g>
old_end = """          <text x={10} y={30} fill="#94a3b8" fontSize="8" fontFamily="system-ui" opacity="0.7">
            Landslide Risk Surface A Click any cell to inspect
          </text>
        </svg>"""
new_end = """          <text x={10} y={30} fill="#94a3b8" fontSize="8" fontFamily="system-ui" opacity="0.7">
            Landslide Risk Surface - Click any cell to inspect
          </text>
          </g>
        </svg>"""
content = content.replace(old_end, new_end)

# Also there's another variant of this text due to unicode issues
old_end_2 = """          <text x={10} y={30} fill="#94a3b8" fontSize="8" fontFamily="system-ui" opacity="0.7">
            Landslide Risk Surface A Click any cell to inspect
          </text>
        </svg>"""
new_end_2 = """          <text x={10} y={30} fill="#94a3b8" fontSize="8" fontFamily="system-ui" opacity="0.7">
            Landslide Risk Surface - Click any cell to inspect
          </text>
          </g>
        </svg>"""
content = content.replace(old_end_2, new_end_2)

old_end_3 = """          <text x={10} y={30} fill="#94a3b8" fontSize="8" fontFamily="system-ui" opacity="0.7">
            Landslide Risk Surface · Click any cell to inspect
          </text>
        </svg>"""
new_end_3 = """          <text x={10} y={30} fill="#94a3b8" fontSize="8" fontFamily="system-ui" opacity="0.7">
            Landslide Risk Surface - Click any cell to inspect
          </text>
          </g>
        </svg>"""
content = content.replace(old_end_3, new_end_3)

# Remove the historical marker text (corrupted unicode)
content = re.sub(r'<text[^>]+>o\s*<\/text>', '', content)
content = re.sub(r'<text[^>]+>⊗\s*<\/text>', '', content)
content = re.sub(r'<text x=\{cx\} y=\{cy \+ 1\} textAnchor="middle" fill="#ffffff" fontSize="6" opacity="0\.7">.*?<\/text>', '', content)


with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed LandslideMap")
