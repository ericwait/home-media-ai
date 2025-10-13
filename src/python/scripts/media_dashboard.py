#!/usr/bin/env python3
"""
Media Collection Dashboard Generator

Generates an interactive HTML dashboard with statistics and visualizations
from the media database.

Usage:
    python generate_dashboard.py --output dashboard.html
"""

import argparse
import base64
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_engine():
    """Get database engine from environment variable."""
    db_uri = os.getenv("HOME_MEDIA_AI_URI")
    if not db_uri:
        raise ValueError("HOME_MEDIA_AI_URI environment variable not set")
    return create_engine(db_uri)


def create_thumbnail(image_path, max_size=(300, 300)):
    """Create a thumbnail of an image and return as base64 string.

    Args:
        image_path: Path to the image file
        max_size: Maximum dimensions (width, height)

    Returns:
        Base64 encoded thumbnail string, or None if failed
    """
    if not HAS_PIL:
        return None

    try:
        # Try to open the image
        with Image.open(image_path) as img:
            # Convert RGBA to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            # Create thumbnail
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save to bytes
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)

            # Encode as base64
            img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            return f"data:image/jpeg;base64,{img_base64}"

    except Exception as e:
        print(f"  Warning: Failed to create thumbnail for {image_path}: {e}")
        return None


def create_image_gallery_html(image_paths_df):
    """Create HTML for image gallery with thumbnails.

    Args:
        image_paths_df: DataFrame with file_path, camera_make, camera_model, created columns

    Returns:
        HTML string for the gallery
    """
    if image_paths_df.empty:
        return "<div style='text-align: center; padding: 40px; color: gray;'>No 5-star rated images found</div>"

    print(f"\nGenerating thumbnails for {len(image_paths_df)} images...")

    gallery_html = """
    <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; padding: 20px;'>
    """

    for idx, row in image_paths_df.iterrows():
        thumbnail = create_thumbnail(row['file_path'])

        if thumbnail:
            camera_info = f"{row['camera_make']} {row['camera_model']}" if pd.notna(row['camera_make']) else "Unknown"
            date_info = row['created'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['created']) else "Unknown"

            location_info = ""
            if pd.notna(row.get('gps_latitude')) and pd.notna(row.get('gps_longitude')):
                location_info = f"&#128205; ({row['gps_latitude']:.4f}, {row['gps_longitude']:.4f})"

            gallery_html += f"""
            <div style='border: 2px solid #ddd; border-radius: 8px; overflow: hidden; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
                <img src='{thumbnail}' style='width: 100%; height: 200px; object-fit: cover;'>
                <div style='padding: 10px; font-size: 12px;'>
                    <div style='font-weight: bold; color: #333;'>&#11237;&#11237;&#11237;&#11237;&#11237;</div>
                    <div style='color: #666; margin-top: 4px;'>{camera_info}</div>
                    <div style='color: #999; margin-top: 2px;'>{date_info}</div>
                    <div style='color: #999; margin-top: 2px;'>{location_info}</div>
                </div>
            </div>
            """
            print(f"  ✓ Thumbnail {idx+1}/{len(image_paths_df)}")

    gallery_html += "</div>"
    return gallery_html


def fetch_media_stats(engine):
    """Fetch comprehensive media statistics from database."""

    queries = {
        'overview': """
            SELECT
                COUNT(*) as total_files,
                COUNT(DISTINCT camera_make) as unique_cameras,
                SUM(file_size) / (1024*1024*1024) as total_size_gb,
                MIN(created) as earliest_photo,
                MAX(created) as latest_photo,
                COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as rated_photos,
                COUNT(CASE WHEN is_original = TRUE THEN 1 END) as originals,
                COUNT(CASE WHEN is_original = FALSE THEN 1 END) as derivatives
            FROM media
        """,

        'by_camera': """
            SELECT
                COALESCE(camera_make, 'Unknown') as make,
                COALESCE(camera_model, 'Unknown') as model,
                CONCAT(
                    COALESCE(camera_make, 'Unknown'),
                    ' ',
                    COALESCE(camera_model, 'Unknown')
                ) as camera,
                COUNT(*) as count,
                AVG(file_size) / (1024*1024) as avg_size_mb
            FROM media
            WHERE is_original = TRUE
            GROUP BY camera_make, camera_model
            ORDER BY count DESC
        """,

        'by_rating': """
            SELECT
                COALESCE(rating, 0) as rating,
                COUNT(*) as count
            FROM media
            WHERE is_original = TRUE
            GROUP BY rating
            ORDER BY rating
        """,

        'by_month': """
            SELECT
                DATE_FORMAT(created, '%Y-%m') as month,
                COUNT(*) as count,
                SUM(file_size) / (1024*1024*1024) as size_gb
            FROM media
            WHERE is_original = TRUE
            GROUP BY DATE_FORMAT(created, '%Y-%m')
            ORDER BY month
        """,

        'by_lens': """
            SELECT
                COALESCE(lens_model, 'Unknown') as lens,
                COUNT(*) as count
            FROM media
            WHERE is_original = TRUE
              AND lens_model IS NOT NULL
            GROUP BY lens_model
            ORDER BY count DESC
            LIMIT 10
        """,

        'gps_locations': """
            SELECT
                gps_latitude,
                gps_longitude,
                file_path,
                camera_make,
                camera_model,
                rating,
                created
            FROM media
            WHERE is_original = TRUE
              AND gps_latitude IS NOT NULL
              AND gps_longitude IS NOT NULL
        """,

        'camera_rating_matrix': """
            SELECT
                CONCAT(
                    COALESCE(TRIM(camera_make), 'Unknown'),
                    ' ',
                    COALESCE(TRIM(camera_model), 'Unknown')
                ) as camera,
                COALESCE(rating, 0) as rating,
                COUNT(*) as count
            FROM media
            WHERE is_original = TRUE
            GROUP BY
                CONCAT(
                    COALESCE(TRIM(camera_make), 'Unknown'),
                    ' ',
                    COALESCE(TRIM(camera_model), 'Unknown')
                ),
                COALESCE(rating, 0)
            ORDER BY camera, rating
        """,

        'top_rated_images': """
            SELECT
                file_path,
                camera_make,
                camera_model,
                created,
                gps_latitude,
                gps_longitude
            FROM media
            WHERE is_original = TRUE
              AND rating = 5
            ORDER BY RAND()
            LIMIT 12
        """,

        'time_of_day': """
            SELECT
                HOUR(created) as hour,
                COUNT(*) as count,
                AVG(COALESCE(rating, 0)) as avg_rating
            FROM media
            WHERE is_original = TRUE
            GROUP BY HOUR(created)
            ORDER BY hour
        """
    }

    results = {}
    with engine.begin() as conn:
        for name, query in queries.items():
            df = pd.read_sql(text(query), conn)
            results[name] = df

    return results


def create_dashboard(stats):
    """Create interactive dashboard with all visualizations."""

    # Create subplot layout - now with 5 rows
    fig = make_subplots(
        rows=5, cols=2,
        subplot_titles=(
            'Camera Models Distribution',
            'Rating Distribution',
            'Photos per Month Timeline',
            'Time of Day Analysis',
            'Top 10 Lenses Used',
            'Camera-to-Rating Distribution',
            'Geographic Photo Locations',
            'Collection Overview',
            '5-Star Gallery (shown below)',
            ''
        ),
        specs=[
            [{'type': 'domain'}, {'type': 'bar'}],
            [{'type': 'scatter'}, {'type': 'scatter'}],
            [{'type': 'bar'}, {'type': 'heatmap'}],
            [{'type': 'scattermapbox', 'colspan': 2}, None],
            [{'type': 'table', 'colspan': 2}, None]
        ],
        row_heights=[0.20, 0.20, 0.20, 0.25, 0.15],
        vertical_spacing=0.10,
        horizontal_spacing=0.15
    )

    # 1. Camera Models - Sunburst instead of pie
    camera_df = stats['by_camera']
    fig.add_trace(
        go.Sunburst(
            labels=camera_df['camera'].tolist(),
            parents=[''] * len(camera_df),
            values=camera_df['count'].tolist(),
            textinfo='label+percent entry',
            marker=dict(colorscale='Viridis'),
            hovertemplate='<b>%{label}</b><br>Photos: %{value}<br>%{percent}<extra></extra>'
        ),
        row=1, col=1
    )

    # 2. Rating Distribution
    rating_df = stats['by_rating']
    rating_labels = ['Unrated' if r == 0 else f'{"★" * int(r)}' for r in rating_df['rating']]
    colors = ['gray' if r == 0 else f'rgb({255-r*30}, {140+r*20}, {0})'
              for r in rating_df['rating']]

    fig.add_trace(
        go.Bar(
            x=rating_labels,
            y=rating_df['count'],
            marker=dict(color=colors),
            text=rating_df['count'],
            textposition='outside',
            hovertemplate='%{x}<br>Count: %{y}<extra></extra>'
        ),
        row=1, col=2
    )

    # 3. Photos per Month Timeline
    month_df = stats['by_month']
    fig.add_trace(
        go.Scatter(
            x=pd.to_datetime(month_df['month']),
            y=month_df['count'],
            mode='lines+markers',
            fill='tozeroy',
            marker=dict(size=6, color='rgb(55, 83, 109)'),
            line=dict(color='rgb(55, 83, 109)', width=2),
            hovertemplate='%{x|%B %Y}<br>Photos: %{y}<extra></extra>'
        ),
        row=2, col=1
    )

    # 4. Time of Day Analysis - with dual y-axis
    tod_df = stats['time_of_day']

    # Create subplot with secondary y-axis capability
    # We'll manually create this as a special case
    from plotly.subplots import make_subplots as make_subplots_internal

    # Add bar chart for photo count
    fig.add_trace(
        go.Bar(
            x=tod_df['hour'],
            y=tod_df['count'],
            name='Photo Count',
            marker=dict(color='rgba(55, 83, 109, 0.7)'),
            hovertemplate='Hour: %{x}:00<br>Photos: %{y}<extra></extra>'
        ),
        row=2, col=2
    )

    # Add line chart for average rating on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=tod_df['hour'],
            y=tod_df['avg_rating'],
            name='Avg Rating',
            mode='lines+markers',
            line=dict(color='rgb(255, 127, 14)', width=3),
            marker=dict(size=10, color='rgb(255, 127, 14)',
                       line=dict(color='white', width=2)),
            hovertemplate='Hour: %{x}:00<br>Avg Rating: %{y:.2f}★<extra></extra>',
            yaxis='y4'  # Secondary y-axis
        ),
        row=2, col=2
    )

    # 5. Top Lenses
    lens_df = stats['by_lens']
    fig.add_trace(
        go.Bar(
            y=lens_df['lens'],
            x=lens_df['count'],
            orientation='h',
            marker=dict(color='rgb(158, 202, 225)'),
            text=lens_df['count'],
            textposition='outside',
            hovertemplate='%{y}<br>Photos: %{x}<extra></extra>'
        ),
        row=3, col=1
    )

    # 6. Camera-to-Rating Heatmap with better color scaling
    cr_df = stats['camera_rating_matrix']

    # Handle any remaining duplicates by summing counts
    cr_df = cr_df.groupby(['camera', 'rating'], as_index=False)['count'].sum()

    # Pivot data for heatmap
    pivot_df = cr_df.pivot(index='camera', columns='rating', values='count').fillna(0)
    rating_labels = ['Unrated' if c == 0 else f'{"★" * int(c)}' for c in pivot_df.columns]

    # Apply log10 transformation for better color distribution (add 1 to handle zeros)
    z_data = pivot_df.values
    z_log = np.log10(z_data + 1)  # log10(x+1) transformation

    # Create custom hover text with original values
    hover_text = []
    for i, camera in enumerate(pivot_df.index):
        hover_row = []
        for j, rating in enumerate(rating_labels):
            count = int(z_data[i, j])
            hover_row.append(f'Camera: {camera}<br>Rating: {rating}<br>Photos: {count}')
        hover_text.append(hover_row)

    fig.add_trace(
        go.Heatmap(
            z=z_log,
            x=rating_labels,
            y=pivot_df.index,
            colorscale='YlOrRd',
            text=hover_text,
            hovertemplate='%{text}<extra></extra>',
            colorbar=dict(
                title=dict(text="Log₁₀<br>Count", side="right"),
                thickness=15,
                len=0.7,
                y=0.35,
                yanchor='middle',
                tickmode='array',
                tickvals=[0, 1, 2, 3, 4],
                ticktext=['0', '10', '100', '1K', '10K']
            )
        ),
        row=3, col=2
    )

    # 7. Geographic Map
    gps_df = stats['gps_locations']

    if not gps_df.empty:
        # Create hover text with details
        hover_text = [
            f"<b>{row['camera_make']} {row['camera_model']}</b><br>" +
            f"Date: {row['created'].strftime('%Y-%m-%d')}<br>" +
            f"Rating: {'★' * int(row['rating']) if pd.notna(row['rating']) and row['rating'] > 0 else 'Unrated'}<br>" +
            f"Location: ({row['gps_latitude']:.4f}, {row['gps_longitude']:.4f})"
            for _, row in gps_df.iterrows()
        ]

        # Color by rating
        colors = []
        for rating in gps_df['rating']:
            if pd.isna(rating) or rating == 0:
                colors.append('gray')
            else:
                # Scale from yellow (1 star) to red (5 stars)
                colors.append(f'rgb({255-rating*10}, {140+rating*15}, {0})')

        fig.add_trace(
            go.Scattermapbox(
                lat=gps_df['gps_latitude'],
                lon=gps_df['gps_longitude'],
                mode='markers',
                marker=dict(
                    size=8,
                    color=colors,
                    opacity=0.7
                ),
                text=hover_text,
                hovertemplate='%{text}<extra></extra>'
            ),
            row=4, col=1
        )

        # Calculate center and zoom for map
        center_lat = gps_df['gps_latitude'].mean()
        center_lon = gps_df['gps_longitude'].mean()

        # Calculate zoom level based on data spread
        lat_range = gps_df['gps_latitude'].max() - gps_df['gps_latitude'].min()
        lon_range = gps_df['gps_longitude'].max() - gps_df['gps_longitude'].min()
        max_range = max(lat_range, lon_range)

        # Rough zoom calculation
        if max_range > 50:
            zoom = 2
        elif max_range > 20:
            zoom = 4
        elif max_range > 10:
            zoom = 5
        elif max_range > 5:
            zoom = 6
        elif max_range > 1:
            zoom = 8
        else:
            zoom = 10

        fig.update_mapboxes(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom,
            row=4, col=1
        )
    else:
        # No GPS data - add annotation
        fig.add_annotation(
            text="No GPS data available",
            xref="x7", yref="y7",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray"),
            row=4, col=1
        )

    # 8. Overview Table
    overview = stats['overview'].iloc[0]
    gps_count = len(stats['gps_locations'])
    five_star_count = len(stats['top_rated_images'])

    overview_data = [
        ['Total Files', f"{int(overview['total_files']):,}"],
        ['Original Files', f"{int(overview['originals']):,}"],
        ['Derivative Files', f"{int(overview['derivatives']):,}"],
        ['Total Storage', f"{overview['total_size_gb']:.2f} GB"],
        ['Geotagged Photos', f"{gps_count:,} ({gps_count/overview['originals']*100:.1f}%)"],
        ['Rated Photos', f"{int(overview['rated_photos']):,} ({overview['rated_photos']/overview['total_files']*100:.1f}%)"],
        ['5-Star Photos', f"{five_star_count:,}"],
        ['Unique Cameras', f"{int(overview['unique_cameras'])}"],
        ['Date Range', f"{overview['earliest_photo'].strftime('%Y-%m-%d')} to {overview['latest_photo'].strftime('%Y-%m-%d')}"],
        ['Years Covered', f"{(overview['latest_photo'] - overview['earliest_photo']).days / 365.25:.1f}"]
    ]

    fig.add_trace(
        go.Table(
            header=dict(
                values=['<b>Metric</b>', '<b>Value</b>'],
                fill_color='rgb(55, 83, 109)',
                font=dict(color='white', size=14),
                align='left'
            ),
            cells=dict(
                values=[[row[0] for row in overview_data],
                       [row[1] for row in overview_data]],
                fill_color=['rgb(235, 240, 245)', 'white'],
                font=dict(size=12),
                align='left',
                height=25
            )
        ),
        row=5, col=1
    )

    # Update layout
    fig.update_layout(
        title={
            'text': '📸 Media Collection Dashboard',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 24, 'color': 'rgb(55, 83, 109)'}
        },
        showlegend=False,
        height=2000,
        plot_bgcolor='white',
        paper_bgcolor='rgb(243, 246, 249)',
        font=dict(family="Arial, sans-serif"),
        # Configure secondary y-axis for time of day plot
        yaxis4=dict(
            title='Avg Rating (★)',
            overlaying='y3',
            side='right',
            range=[0, 5],
            showgrid=False,
            zeroline=False
        )
    )

    # Update axes
    fig.update_xaxes(title_text="Month", row=2, col=1, showgrid=True, gridcolor='lightgray')
    fig.update_yaxes(title_text="Photo Count", row=2, col=1, showgrid=True, gridcolor='lightgray')

    fig.update_xaxes(title_text="Hour of Day", row=2, col=2, showgrid=True, gridcolor='lightgray', dtick=2)
    fig.update_yaxes(title_text="Photo Count", row=2, col=2, showgrid=True, gridcolor='lightgray')

    fig.update_xaxes(title_text="Photo Count", row=3, col=1, showgrid=True, gridcolor='lightgray')

    fig.update_xaxes(title_text="Rating", row=3, col=2, showgrid=False)
    fig.update_yaxes(title_text="Camera Model", row=3, col=2, showgrid=False)

    return fig


def generate_html_report(stats, output_file):
    """Generate standalone HTML report."""

    fig = create_dashboard(stats)

    # Generate image gallery HTML
    gallery_html = create_image_gallery_html(stats['top_rated_images'])

    # Add timestamp footer
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Media Collection Dashboard</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f3f6f9;
            }}
            .gallery-section {{
                margin-top: 30px;
                padding: 20px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .gallery-title {{
                font-size: 24px;
                font-weight: bold;
                color: rgb(55, 83, 109);
                margin-bottom: 20px;
                text-align: center;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                padding: 10px;
                color: #666;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        {fig.to_html(include_plotlyjs='cdn', full_html=False)}
        <div class="gallery-section">
            <div class="gallery-title">&#11088; 5-Star Photo Gallery</div>
            {gallery_html}
        </div>
        <div class="footer">
            Generated: {timestamp} | Home Media AI Dashboard
        </div>
    </body>
    </html>
    """

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_template)

    print(f"\n✓ Dashboard saved to: {output_file}")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate interactive media collection dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--output',
        default='media_dashboard.html',
        help='Output HTML file path (default: media_dashboard.html)'
    )

    args = parser.parse_args()

    print("="*60)
    print("Media Collection Dashboard Generator")
    print("="*60)

    # Connect to database
    print("\nConnecting to database...")
    try:
        engine = get_engine()
        print(f"✓ Connected to: {engine.url.database}")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return

    # Fetch statistics
    print("\nFetching media statistics...")
    try:
        stats = fetch_media_stats(engine)
        print(f"✓ Fetched data from {len(stats)} queries")

        # Debug: Check for data issues
        if 'camera_rating_matrix' in stats:
            cr_df = stats['camera_rating_matrix']
            duplicates = cr_df[cr_df.duplicated(subset=['camera', 'rating'], keep=False)]
            if not duplicates.empty:
                print(f"  ⚠ Warning: Found {len(duplicates)} duplicate camera-rating entries")
                print(f"    Duplicates: {duplicates[['camera', 'rating']].drop_duplicates().to_dict('records')}")

    except Exception as e:
        print(f"✗ Failed to fetch statistics: {e}")
        import traceback
        traceback.print_exc()
        return

    # Generate dashboard
    print("\nGenerating dashboard...")
    try:
        generate_html_report(stats, args.output)
        print(f"\n✓ Dashboard generated successfully!")
        print(f"\nOpen in browser: file://{Path(args.output).absolute()}")
    except Exception as e:
        print(f"✗ Failed to generate dashboard: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "="*60)


if __name__ == '__main__':
    main()
