path = r"C:\Users\Ravichandran\Downloads\TERRAPULSE\apps\terrapulse\frontend\src\features\GeospatialViewer.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject pointsGeoJSON right below riskGeoJSON
# riskGeoJSON ends with:
#        })
#      };
#    }, [cells]);
# Let's just find that ending using regex.

import re

# Add pointsGeoJSON
old_deps = "      };\n    }, [cells]);"
new_deps = """      };
    }, [cells]);

  const pointsGeoJSON = React.useMemo(() => {
    return {
      type: 'FeatureCollection',
      features: cells.map(cell => {
        let color = '#22c55e';
        if (cell.risk_level === 'moderate' || cell.risk_level === 'MODERATE') color = '#eab308';
        if (cell.risk_level === 'high' || cell.risk_level === 'HIGH') color = '#f97316';
        if (cell.risk_level === 'critical' || cell.risk_level === 'CRITICAL') color = '#ef4444';
        
        return {
          type: 'Feature',
          properties: { ...cell, color },
          geometry: {
            type: 'Point',
            coordinates: [cell.centroid_lon, cell.centroid_lat]
          }
        };
      })
    };
  }, [cells]);"""

content = content.replace(old_deps, new_deps)

# 2. Add filters and new layers in MapLibre
# We need to find the <Source id="risk-data" ...> block

old_source = """        <Source id="risk-data" type="geojson" data={riskGeoJSON}>
          <Layer
            id="risk-fill"
            type="fill"
            paint={{
              'fill-color': ['get', 'color'],
              'fill-opacity': ['get', 'opacity']
            }}
          />
          <Layer
            id="risk-outline"
            type="line"
            paint={{
              'line-color': ['get', 'color'],
              'line-width': 2,
              'line-opacity': 0.8
            }}
          />
        </Source>"""

new_source = """        {/* Polygons: Only show for selected cell */}
        <Source id="risk-data" type="geojson" data={riskGeoJSON}>
          <Layer
            id="risk-fill"
            type="fill"
            filter={['==', 'location_id', selectedCell?.location_id || '']}
            paint={{
              'fill-color': ['get', 'color'],
              'fill-opacity': ['get', 'opacity']
            }}
          />
          <Layer
            id="risk-outline"
            type="line"
            filter={['==', 'location_id', selectedCell?.location_id || '']}
            paint={{
              'line-color': ['get', 'color'],
              'line-width': 2,
              'line-opacity': 0.8
            }}
          />
        </Source>

        {/* Points (Circles): Only show for UNSELECTED cells */}
        <Source id="risk-points" type="geojson" data={pointsGeoJSON}>
          {/* Outer gray ring */}
          <Layer
            id="risk-circle-outer"
            type="circle"
            filter={['!=', 'location_id', selectedCell?.location_id || '']}
            paint={{
              'circle-color': '#64748b',
              'circle-radius': 9,
              'circle-opacity': 0.9,
              'circle-pitch-alignment': 'map'
            }}
          />
          {/* Inner risk color fill */}
          <Layer
            id="risk-circle-inner"
            type="circle"
            filter={['!=', 'location_id', selectedCell?.location_id || '']}
            paint={{
              'circle-color': ['get', 'color'],
              'circle-radius': 6.5,
              'circle-opacity': 1.0,
              'circle-pitch-alignment': 'map'
            }}
          />
        </Source>"""

content = content.replace(old_source, new_source)

# Update the interactiveLayerIds
old_interactive = "interactiveLayerIds={['risk-fill']}"
new_interactive = "interactiveLayerIds={['risk-fill', 'risk-circle-outer', 'risk-circle-inner']}"
content = content.replace(old_interactive, new_interactive)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("GeospatialViewer updated")
