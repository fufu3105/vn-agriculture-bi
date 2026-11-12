"""BP2 entry point. Replace the content here when the BP2 mart is available."""
import streamlit as st

st.markdown('<div class="eyebrow">BP2 / DIAGNOSTIC ANALYTICS</div>', unsafe_allow_html=True)
st.title("Explaining production changes")
st.markdown("Break down production changes by sown area and yield, and compare provinces and periods that need attention.")
st.info("The BP2 dashboard is in development. Analysis results are not available yet.", icon=":material/construction:")
st.subheader("Key question")
st.markdown("Are production changes mainly driven by sown area or yield? Which component contributes more in each province and period?")
