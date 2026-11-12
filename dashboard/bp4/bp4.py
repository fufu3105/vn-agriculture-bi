"""BP4 entry point. Replace the content here when the BP4 mart is available."""
import streamlit as st

st.markdown('<div class="eyebrow">BP4 / DIAGNOSTIC ANALYTICS</div>', unsafe_allow_html=True)
st.title("Weather and yield variation")
st.markdown("Compare temperature, rainfall and rice yield by province and year to identify regions that need monitoring.")
st.info("The BP4 dashboard is in development. Weather and yield analysis results are not available yet.", icon=":material/construction:")
st.subheader("Key question")
st.markdown("How are temperature and rainfall associated with yield? Which statistical relationships need further investigation before making causal claims?")
