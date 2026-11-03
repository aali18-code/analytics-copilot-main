import React from 'react';
import Plot from 'react-plotly.js';

export default function PlotlyFigure({ figure }) {
  return (
    <Plot
      data={figure.data || []}
      layout={{ ...figure.layout, autosize: true, margin: { t: 55, r: 24, b: 50, l: 55, ...(figure.layout?.margin || {}) }, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent' }}
      frames={figure.frames || []}
      config={{ responsive: true, displaylogo: false, toImageButtonOptions: { format: 'png', filename: 'analytics_chart', scale: 2 } }}
      useResizeHandler
      style={{ width: '100%', height: 390 }}
    />
  );
}
