path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\LandslideMap.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_block = """                {/* Risk fill rectangle */}
                <rect
                  x={Math.min(x1, x2)}
                  y={Math.min(y1, y2)}
                  width={w}
                  height={h}
                  fill={color}
                  fillOpacity={isSelected ? Math.min(opacity + 0.25, 0.95) : opacity}
                  rx="3"
                  stroke={isSelected ? '#ffffff' : color}
                  strokeOpacity={isSelected ? 0.9 : 0.4}
                  strokeWidth={isSelected ? 2 : 1}
                />

                {/* Pulsing ring for critical cells */}
                {isCritical && (
                  <rect
                    x={Math.min(x1, x2) - 3}
                    y={Math.min(y1, y2) - 3}
                    width={w + 6}
                    height={h + 6}
                    fill="none"
                    stroke={color}
                    strokeOpacity="0.4"
                    strokeWidth="2"
                    rx="5"
                  >
                    <animate attributeName="stroke-opacity" values="0.5;0.0;0.5" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="stroke-width" values="2;4;2" dur="2s" repeatCount="indefinite" />
                  </rect>
                )}

                {/* Center dot */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHighRisk ? 5 : 3.5}
                  fill={color}
                  fillOpacity="0.95"
                  stroke="#ffffff"
                  strokeOpacity="0.6"
                  strokeWidth="0.8"
                />"""

new_block = """                {isSelected ? (
                  <>
                    {/* Risk fill rectangle */}
                    <rect
                      x={Math.min(x1, x2)}
                      y={Math.min(y1, y2)}
                      width={w}
                      height={h}
                      fill={color}
                      fillOpacity={Math.min(opacity + 0.25, 0.95)}
                      rx="3"
                      stroke="#ffffff"
                      strokeOpacity="0.9"
                      strokeWidth="2"
                    />

                    {/* Pulsing ring for critical cells */}
                    {isCritical && (
                      <rect
                        x={Math.min(x1, x2) - 3}
                        y={Math.min(y1, y2) - 3}
                        width={w + 6}
                        height={h + 6}
                        fill="none"
                        stroke={color}
                        strokeOpacity="0.4"
                        strokeWidth="2"
                        rx="5"
                      >
                        <animate attributeName="stroke-opacity" values="0.5;0.0;0.5" dur="2s" repeatCount="indefinite" />
                        <animate attributeName="stroke-width" values="2;4;2" dur="2s" repeatCount="indefinite" />
                      </rect>
                    )}

                    {/* Center dot for selected */}
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isHighRisk ? 5 : 3.5}
                      fill="#ffffff"
                    />
                  </>
                ) : (
                  <>
                    {/* Unselected circle shape with gray outer ring and risk color inner fill */}
                    <circle 
                      cx={cx} 
                      cy={cy} 
                      r={9} 
                      fill={color} 
                      fillOpacity="0.85"
                      stroke="#64748b" 
                      strokeWidth="2.5" 
                    />
                    
                    {/* Pulsing ring for critical cells even when unselected */}
                    {isCritical && (
                      <circle cx={cx} cy={cy} r={13} fill="none" stroke={color} strokeOpacity="0.5" strokeWidth="2">
                        <animate attributeName="r" values="13;17;13" dur="2s" repeatCount="indefinite" />
                        <animate attributeName="stroke-opacity" values="0.5;0.0;0.5" dur="2s" repeatCount="indefinite" />
                      </circle>
                    )}
                  </>
                )}"""

content = content.replace(old_block, new_block)
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("LandslideMap updated")
