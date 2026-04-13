import streamlit as st
import sqlite3
import pandas as pd

# --- Configuration ---
DATABASE_NAME = "cinema_bookings.db"
SEAT_ROWS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
NUM_COLS = 10
SEAT_PRICE = 15.00

# --- 1. Database Functions (SQLite) ---

def initialize_database():
    """Initializes the SQLite database with movie and booking tables."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create Movies Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            time TEXT NOT NULL,
            seats_total INTEGER NOT NULL
        )
    """)

    # Create Bookings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INTEGER PRIMARY KEY,
            movie_id INTEGER NOT NULL,
            seat_id TEXT NOT NULL,
            is_booked BOOLEAN NOT NULL DEFAULT 1,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    """)

    # Insert sample movies only if the table is empty
    cursor.execute("SELECT COUNT(*) FROM movies")
    if cursor.fetchone()[0] == 0:
        movies_data = [
            ("Cosmic Drift (10:00 AM)", "10:00 AM", len(SEAT_ROWS) * NUM_COLS),
            ("The Silent Forest (1:30 PM)", "1:30 PM", len(SEAT_ROWS) * NUM_COLS),
            ("Cyberpunk Tokyo (7:00 PM)", "7:00 PM", len(SEAT_ROWS) * NUM_COLS), # <-- COMMA ADDED HERE (The Fix!)
            ("Spiderman No way home (10:00 PM)", "10:00 PM", len(SEAT_ROWS) * NUM_COLS),
            ("John Wick 7 (1:30 AM)", "1:30 AM", len(SEAT_ROWS) * NUM_COLS),
            ("Anaconda 5 (7:00 AM)", "7:00 AM", len(SEAT_ROWS) * NUM_COLS)
        ]
        # Note: We insert the title with time for display, but time is also a separate column
        cursor.executemany("INSERT INTO movies (title, time, seats_total) VALUES (?, ?, ?)", movies_data)

    conn.commit()
    conn.close()

def get_movies():
    """Retrieves all available movies and showtimes."""
    conn = sqlite3.connect(DATABASE_NAME)
    df = pd.read_sql_query("SELECT id, title, time FROM movies", conn)
    conn.close()
    return df

def get_booked_seats(movie_id):
    """Retrieves all booked seats for a specific movie ID."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT seat_id FROM bookings WHERE movie_id = ?", (movie_id,))
    booked_seats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return booked_seats

def book_seats(movie_id, selected_seats):
    """Inserts the selected seats into the bookings table using a transaction-like approach."""
    if not selected_seats:
        return False, "No seats selected."

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    try:
        # Check for concurrent booking (simple check before insert)
        existing_bookings = get_booked_seats(movie_id)
        conflict_seats = [seat for seat in selected_seats if seat in existing_bookings]

        if conflict_seats:
            conn.close()
            # This simulates a race condition where another user booked the seat
            return False, f"Booking conflict! Seat(s) {', '.join(conflict_seats)} were just booked by another user."

        # Insert new bookings
        insert_data = [(movie_id, seat) for seat in selected_seats]
        cursor.executemany("INSERT INTO bookings (movie_id, seat_id) VALUES (?, ?)", insert_data)

        conn.commit()
        return True, f"Successfully booked {len(selected_seats)} seat(s)!"

    except Exception as e:
        conn.rollback()
        return False, f"An error occurred during booking: {e}"

    finally:
        conn.close()

# --- 2. Streamlit Application Functions ---

def render_seating_chart(movie_id, booked_seats):
    """Renders the interactive seating chart using Streamlit columns and returns selected seats."""
    st.subheader("Seating Chart")
    
    # Custom CSS for the screen visual
    st.markdown("""
        <style>
            .screen-box {
                background-color:#444; 
                color:white; 
                padding:15px; 
                text-align:center; 
                border-radius:10px 10px 0 0; 
                margin-bottom: 20px;
                font-weight: bold;
                letter-spacing: 2px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.5);
            }
        </style>
        <div class="screen-box">SCREEN (Front)</div>
    """, unsafe_allow_html=True)
    
    # Use session state to manage selected seats across reruns
    if 'selected_seats_map' not in st.session_state:
        st.session_state['selected_seats_map'] = {}

    selected_seats_for_movie = []
    
    # Setup columns: 1 for row letter + NUM_COLS for seats
    chart_cols = st.columns([0.5] + [1] * NUM_COLS) 

    # Header Row (Column Numbers)
    chart_cols[0].markdown("") # Empty for row letter column
    for col_idx in range(NUM_COLS):
        chart_cols[col_idx + 1].markdown(f"**{col_idx + 1}**", help=f"Column {col_idx + 1}", unsafe_allow_html=True)

    # Seat Chart
    for row_idx, row_letter in enumerate(SEAT_ROWS):
        # Column for the row letter
        chart_cols[0].markdown(f"**{row_letter}**", unsafe_allow_html=True)
        
        for col_idx in range(NUM_COLS):
            seat_id = f"{row_letter}{col_idx + 1}"
            is_booked = seat_id in booked_seats
            
            # Unique key for each seat's state
            seat_key = f"seat_{movie_id}_{seat_id}"
            
            # Initialize seat state for the current movie and seat
            if seat_key not in st.session_state['selected_seats_map']:
                st.session_state['selected_seats_map'][seat_key] = False

            # Determine button appearance
            if is_booked:
                seat_label = "❌"
                tooltip = "Booked"
                disabled = True
            elif st.session_state['selected_seats_map'][seat_key]:
                seat_label = "✅"
                tooltip = "Selected"
                disabled = False
            else:
                seat_label = "⚪"
                tooltip = "Available"
                disabled = False

            # Create a custom button/toggle in the cell
            if chart_cols[col_idx + 1].button(
                seat_label, 
                key=seat_key, 
                help=tooltip, 
                disabled=disabled
            ):
                # Toggle selection state on click if not booked
                if not is_booked:
                    st.session_state['selected_seats_map'][seat_key] = not st.session_state['selected_seats_map'][seat_key]
                    # Rerunning to update the chart visuals immediately
                    st.rerun()

            # If the seat is currently selected, add it to the return list
            if st.session_state['selected_seats_map'][seat_key]:
                selected_seats_for_movie.append(seat_id)
                
    st.markdown("---")
    st.caption("Legend: ⚪ = Available, ✅ = Selected, ❌ = Booked")
    
    return selected_seats_for_movie

def main():
    """Main Streamlit application function."""
    st.set_page_config(page_title="Cinema Ticketing System", layout="wide")
    st.title(" Movie Ticket Booking")
    st.markdown("A simple, functional ticketing system.")

    # Initialize the database on first run
    initialize_database()

    # --- 1. Movie Selection ---
    movies_df = get_movies()
    movie_titles = movies_df['title'].tolist()
    
    selected_title = st.selectbox("Select a Movie and Show Time:", movie_titles, key="movie_select")
    
    # Get the corresponding movie ID
    selected_movie = movies_df[movies_df['title'] == selected_title].iloc[0]
    movie_id = selected_movie['id']

    st.info(f"Movie: **{selected_movie['title']}** | Price per seat: **${SEAT_PRICE:.2f}**")
    st.markdown("---")

    # --- 2. Seating Chart Display ---
    # This must be run before the booking summary to populate the selected_seats list
    booked_seats = get_booked_seats(movie_id)
    selected_seats = render_seating_chart(movie_id, booked_seats)
    
    # --- 3. Summary and Booking ---
    st.markdown("---")
    st.header("Booking Summary")
    
    num_seats = len(selected_seats)
    total_cost = num_seats * SEAT_PRICE
    
    col1, col2 = st.columns(2)
    col1.metric("Selected Seats", num_seats)
    col2.metric("Total Cost", f"${total_cost:.2f}")

    if num_seats > 0:
        st.success(f"Seats selected: **{', '.join(selected_seats)}**")
    else:
        st.markdown("Please select seats above.")


    if st.button("Confirm and Pay Now", key="book_button", disabled=(num_seats == 0), type="primary"):
        # Attempt to book the seats
        with st.spinner('Processing your booking...'):
            success, message = book_seats(movie_id, selected_seats)
            
            if success:
                st.success(f"🎉 Booking Successful! {message}")
                # Clear all stored selected seats to reset the chart state
                if 'selected_seats_map' in st.session_state:
                    del st.session_state['selected_seats_map']
                # Rerun the app to update the chart with new permanent bookings
                st.rerun() 
            else:
                st.error(f"⚠️ Booking Failed: {message}")
                # Don't clear session state on failure so the user can see their conflict
                st.warning("Please check the chart for any conflicts (red X's) and try selecting available seats.")


# Run the application
if __name__ == "__main__":
    main()
