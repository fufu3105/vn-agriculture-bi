"""Presentation helpers for Section 2.1; reuse existing alignment/statistics."""
import numpy as np
import plotly.express as px
from src.bp4 import bi
from src.bp4.production_weather import add_regional_trends


def aligned_observations(source,climate,outcome,lag,group):
    f=bi.align_lag(source,climate,outcome,lag,group)
    return f.merge(source[[group,'year','yield_value','production_ton']],on=[group,'year'],how='left',validate='one_to_one')


def scatter_view(frame,climate,form,outcome,method,region=None,show_line=False,minimum=8):
    xlabel=(('Temperature anomaly (°C)' if form=='anomaly' else 'Average temperature (°C)') if climate=='Temperature'
            else ('Rainfall anomaly (%)' if form=='anomaly' else 'Annual rainfall (mm)'))
    label='Yield change (%)' if outcome=='yield_change_pct' else 'Production change (%)'
    actual='yield_value' if outcome=='yield_change_pct' else 'production_ton'
    actual_label='Actual Yield (t/ha)' if actual=='yield_value' else 'Actual Production (tonnes)'
    fig=px.scatter(frame,x='climate_value',y=outcome,color='region',
                   custom_data=['region','year','climate_year',actual,'yield_change_pct','production_change_pct','area_change_pct'],
                   labels={'climate_value':xlabel,outcome:label},title=climate+' vs '+label)
    hover=('Region: %{customdata[0]}<br>Outcome Year: %{customdata[1]}<br>Climate Year: %{customdata[2]:.0f}'
           '<br>Climate Value - '+xlabel+': %{x:.2f}<br>Yield Change: %{customdata[4]:+.2f}%<br>Production Change: %{customdata[5]:+.2f}%'
           '<br>'+actual_label+': %{customdata[3]:,.3f}<br>Area Change: %{customdata[6]:+.2f}%<extra></extra>')
    for trace in fig.data:
        trace.hovertemplate=hover
        trace.marker.opacity=1 if region is None or trace.name==region else .13
        trace.marker.size=9 if region is not None and trace.name==region else 6
    selected=frame[frame.region.eq(region)] if region is not None else frame.iloc[:0]
    result=bi.correlation(selected,'climate_value',outcome,method,minimum)
    coefficient=result['coefficient']
    result['direction']='N/A' if not np.isfinite(coefficient) else 'Positive' if coefficient>0 else 'Negative' if coefficient<0 else 'No rank/linear association'
    result['region']=region
    if region is not None:
        fig.data=tuple(t for t in fig.data if t.name!=region)+tuple(t for t in fig.data if t.name==region)
    if show_line and region is not None and np.isfinite(coefficient):
        add_regional_trends(fig,selected,'climate_value',outcome,minimum)
    return fig,result
