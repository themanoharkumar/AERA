"""Main application entry point for the AERA Streamlit Dashboard.

Sets up the visual identity, global layout (Navbar, Sidebar), and manages page routing.
"""

import streamlit as st
import datetime

# 1. Set page configurations (MUST be the first Streamlit command)
st.set_page_config(
    page_title="AERA",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Inject CSS layout rules to stabilize sidebar navigation
st.markdown(
    """
    <style>
        /* Hide default Streamlit multipage sidebar navigation links */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }
        
        /* Disable sidebar collapse button to keep navigation permanently visible */
        [data-testid="sidebar-collapse-button"] {
            display: none !important;
        }
        
        /* Hide default Streamlit decoration elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        [data-testid="stHeader"] {display: none !important;}
        
        /* Adjust layout spacing */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def main() -> None:
    """Orchestrate layout rendering, shared session state initialization, and page routing."""
    # Initialize active page state if not set
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Dashboard"

    # Initialize shared SystemCoordinator via the service layer
    # Import inside main to avoid premature execution during service setup
    from src.dashboard.services.backend import get_backend_gateway
    
    try:
        gateway = get_backend_gateway()
    except Exception as e:
        st.error(f"Backend Initialization Failure: {e}")
        return

    # Render Sidebar Component (left column layout)
    from src.dashboard.components.sidebar import render_sidebar
    render_sidebar()

    # Render Navbar Component (top sticky layout)
    from src.dashboard.components.navbar import render_navbar
    render_navbar(gateway)

    # Dynamic Page Routing based on session state selection
    current = st.session_state.current_page
    
    if current == "Dashboard":
        from src.dashboard.pages.dashboard import render_page
        render_page(gateway)
    elif current == "Live Cameras":
        from src.dashboard.pages.cameras import render_page
        render_page(gateway)
    elif current == "Incidents":
        from src.dashboard.pages.incidents import render_page
        render_page(gateway)
    elif current == "Evidence":
        from src.dashboard.pages.evidence import render_page
        render_page(gateway)
    elif current == "Reports":
        from src.dashboard.pages.reports import render_page
        render_page(gateway)
    elif current == "Alerts":
        from src.dashboard.pages.alerts import render_page
        render_page(gateway)
    elif current == "Analytics":
        from src.dashboard.pages.analytics import render_page
        render_page(gateway)
    elif current == "Settings":
        from src.dashboard.pages.settings import render_page
        render_page(gateway)


if __name__ == "__main__":
    main()
