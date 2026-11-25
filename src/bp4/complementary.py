"""Three complementary regional annual diagnostics. No source ETL or causal claims."""
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.bp4 import bi
from src.bp4.features import OUT, CLIMATE
from src.bp4.features import reference


def associations(frame,outcome,form,method,lag,minimum=8):
    rows=[]
    for name,col in CLIMATE.items():
        aligned=bi.align_lag(frame,col+"_anomaly" if form=="anomaly" else col,outcome,lag)
        for region,g in aligned.groupby('region'):
            valid=g.dropna(subset=['climate_value',outcome])
            result=bi.correlation(g,'climate_value',outcome,method,minimum)
            rows.append(dict(region=region,climate=name,outcome=outcome,method=method,lag=lag,
                             start_year=valid.year.min(),end_year=valid.year.max(),n=result['n'],
                             coefficient=result['coefficient'],status=result['status']))
    return pd.DataFrame(rows)


def terciles(frame,climate,outcome,form='anomaly',lag=0,minimum=8):
    col=CLIMATE[climate]+('_anomaly' if form=='anomaly' else '')
    f=bi.align_lag(frame,col,outcome,lag)
    f['category']=None;rows=[]
    for region,g in f.groupby('region'):
        weather=g.climate_value.replace([np.inf,-np.inf],np.nan).dropna()
        lo,hi=weather.quantile([1/3,2/3]) if len(weather) else (np.nan,np.nan)
        valid=len(weather)>=minimum and weather.nunique()>=3 and lo<hi
        rows.append(dict(region=region,climate=climate,climate_n=len(weather),lower_threshold=lo,upper_threshold=hi,
                         status='Available' if valid else bi.INSUFFICIENT))
        if valid:
            # Equal threshold values enter the lower group; collapsed terciles are unavailable.
            labels=np.select([g.climate_value.le(lo),g.climate_value.le(hi)],['Low','Medium'],default='High')
            f.loc[g.index,'category']=pd.Series(labels,index=g.index).where(g.climate_value.notna())
    plotted=f.dropna(subset=['category',outcome]).copy()
    summaries=[]
    for category in ['Low','Medium','High']:
        values=plotted.loc[plotted.category.eq(category),outcome]
        n=len(values);q1=values.quantile(.25);q3=values.quantile(.75);iqr=q3-q1
        summaries.append(dict(category=category,n=n,mean=values.mean(),median=values.median(),q1=q1,q3=q3,iqr=iqr,
                              minimum=values.min(),maximum=values.max(),
                              lower_whisker=values[values.ge(q1-1.5*iqr)].min(),upper_whisker=values[values.le(q3+1.5*iqr)].max(),
                              status='Available' if n>=3 and values.nunique()>=2 else bi.INSUFFICIENT))
    return plotted,pd.DataFrame(summaries),pd.DataFrame(rows)


def stability(frame,climate,minimum=8):
    col=CLIMATE[climate]+'_anomaly';rows=[]
    for region,g in frame.groupby('region'):
        valid=g[[col,'yield_change_pct','year']].replace([np.inf,-np.inf],np.nan).dropna()
        supported=len(valid)>=max(2,minimum)
        production=g.production_ton.dropna()
        rows.append(dict(region=region,climate_variability=valid[col].std(ddof=1) if supported else np.nan,
                         yield_variability=valid.yield_change_pct.std(ddof=1) if supported else np.nan,
                         mean_production=production.mean(),production_n=len(production),n=len(valid),
                         start_year=valid.year.min(),end_year=valid.year.max(),status='Available' if supported else bi.INSUFFICIENT))
    result=pd.DataFrame(rows)
    valid=result[['climate_variability','yield_variability','mean_production']].notna().all(axis=1)&result.mean_production.gt(0)
    mx=result.loc[valid,'climate_variability'].median();my=result.loc[valid,'yield_variability'].median()
    result['climate_median']=mx;result['yield_median']=my;result['quadrant']=bi.INSUFFICIENT
    for i,row in result[valid].iterrows():
        result.loc[i,'quadrant']=('Low' if row.climate_variability<=mx else 'High')+' climate variability / '+('Low' if row.yield_variability<=my else 'High')+' yield variability'
    return result


def association_figure(frame,regions):
    fig=px.scatter(frame.dropna(subset=['coefficient']),x='coefficient',y='region',color='climate',symbol='climate',
                   color_discrete_map={'Temperature':'#E45756','Rainfall':'#3989C9'},
                   hover_data=['outcome','method','coefficient','n','start_year','end_year'],
                   labels={'coefficient':'Correlation coefficient'},title='Regional Climate Sensitivity Comparison')
    fig.add_vline(x=0,line_dash='dot',line_color='gray');fig.update_xaxes(range=[-1,1])
    fig.update_yaxes(categoryorder='array',categoryarray=regions,autorange='reversed')
    # Missing coefficients remain explicitly visible, rather than becoming zero.
    for i,row in frame[frame.coefficient.isna()].iterrows():
        fig.add_annotation(x=.01,xref='paper',y=row.region,text=row.climate+': N/A (n='+str(row.n)+')',
                           showarrow=False,yshift=9 if row.climate=='Temperature' else -9,xanchor='left')
    return fig


def distribution_figure(points,summary,outcome,climate):
    fig=go.Figure();rng=np.random.default_rng(42)
    for i,row in summary.iterrows():
        color=['#3989C9','#929292','#E4935C'][i]
        custom=[[climate,row.category,row.n,row['mean'],row['median'],row.q1,row.q3,row.minimum,row.maximum]]
        if row.status=='Available':
            fig.add_trace(go.Box(x=[i],q1=[row.q1],median=[row['median']],q3=[row.q3],lowerfence=[row.lower_whisker],upperfence=[row.upper_whisker],
                                name=row.category,marker_color=color,customdata=custom,showlegend=False,boxpoints=False,width=.45,
                                hovertemplate='Climate: %{customdata[0]}<br>Category: %{customdata[1]}<br>n=%{customdata[2]}<br>Mean: %{customdata[3]:.2f}%<br>Median: %{customdata[4]:.2f}%<br>Q1/Q3: %{customdata[5]:.2f} / %{customdata[6]:.2f}%<br>Min/Max: %{customdata[7]:.2f} / %{customdata[8]:.2f}%<extra></extra>'))
        g=points[points.category.eq(row.category)]
        fig.add_trace(go.Scatter(x=i+rng.uniform(-.15,.15,len(g)),y=g[outcome],mode='markers',showlegend=False,
                                marker=dict(color=color,opacity=.45,size=6),customdata=g[['region','year','climate_value']].to_numpy(),
                                hovertemplate='Region: %{customdata[0]}<br>Year: %{customdata[1]}<br>Climate: %{customdata[2]:.2f}<br>Change: %{y:.2f}%<extra></extra>'))
    fig.update_layout(title='Yield Changes Under Different Climate Conditions' if outcome=='yield_change_pct' else 'Production Changes Under Different Climate Conditions',
                      xaxis=dict(tickvals=[0,1,2],ticktext=[f'{r.category} (n={r.n})' for _,r in summary.iterrows()],title=climate+' condition'),
                      yaxis_title=('Yield' if outcome=='yield_change_pct' else 'Production')+' change (%)')
    return fig


def stability_figure(frame,climate):
    valid=frame.dropna(subset=['climate_variability','yield_variability','mean_production'])
    valid=valid[valid.mean_production.gt(0)]
    colors=px.colors.qualitative.Plotly
    names=reference().region.drop_duplicates().tolist()
    mapping={name:colors[i%len(colors)] for i,name in enumerate(sorted(names))}
    fig=px.scatter(valid,x='climate_variability',y='yield_variability',size='mean_production',size_max=48,color='region',color_discrete_map=mapping,
                   hover_data=['n','start_year','end_year','mean_production','quadrant'],title='Regional Climate-Yield Stability Matrix',
                   labels={'climate_variability':'SD of '+climate.lower()+' anomalies ('+('C' if climate=='Temperature' else 'percentage points')+')',
                           'yield_variability':'SD of yield change (percentage points)','mean_production':'Mean annual production (tonnes)'})
    fig.update_traces(marker_sizemode='area',marker_sizemin=5)
    if len(valid):
        mx=valid.climate_variability.median();my=valid.yield_variability.median()
        fig.add_vline(x=mx,line_dash='dot');fig.add_hline(y=my,line_dash='dot')
        fig.update_xaxes(rangemode='tozero');fig.update_yaxes(rangemode='tozero')
        for x,y,text in [(.01,.02,'Low climate / Low yield variability'),(.99,.02,'High climate / Low yield variability'),
                         (.01,.98,'Low climate / High yield variability'),(.99,.98,'High climate / High yield variability')]:
            fig.add_annotation(x=x,y=y,xref='paper',yref='paper',text=text,showarrow=False,
                               xanchor='left' if x<.5 else 'right',font=dict(size=10),bgcolor='rgba(255,255,255,0.7)')
        scale=max(valid.mean_production)/48**2*2
        for tonnes in [valid.mean_production.median(),valid.mean_production.max()]:
            fig.add_trace(go.Scatter(x=[None],y=[None],mode='markers',name=f'{tonnes/1e6:.2f} million tonnes (bubble area)',
                                    marker=dict(size=[tonnes],sizemode='area',sizeref=scale,sizemin=5,color='gray'),hoverinfo='skip'))
    return fig


def main():
    r,_=bi.load_context();c=bi.config();folder=OUT/'complementary';folder.mkdir(parents=True,exist_ok=True)
    tables={'associations':associations(r,'yield_change_pct','anomaly','Pearson',0,c['minimum_n'])}
    for climate in CLIMATE:
        points,summary,quality=terciles(r,climate,'yield_change_pct',minimum=c['minimum_n'])
        tables.update({climate.lower()+'_observations':points,climate.lower()+'_boxes':summary,climate.lower()+'_quality':quality,
                       climate.lower()+'_stability':stability(r,climate,c['minimum_n'])})
    for name,f in tables.items():f.to_parquet(folder/(name+'.parquet'),index=False)
    metadata=dict(period=[2010,2024],reference=[2010,2024],unit='regional annual',outcome='yield_change_pct',lag=0,minimum_n=c['minimum_n'],
                  tables={name:len(f) for name,f in tables.items()},limitations='Descriptive; no independent-year or causal inference')
    (folder/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(metadata))


if __name__=='__main__':main()
