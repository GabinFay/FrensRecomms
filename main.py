import os
import base64
import json
from openai import OpenAI
from Util.MySpotify import MySpotify
import requests
from dotenv import load_dotenv
import shutil

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize Spotify client
spo = MySpotify(
    client_id=os.getenv('SPOTIFY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
    redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI'),
    scope=os.getenv('SPOTIFY_SCOPE')
)

# Function to encode the image to base64
def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to call GPT-4o API with the base64 image and a prompt
def extract_song_info_from_image(base64_image):
    # prompt='extract all the text you can find in this image'
    prompt = "Extract the song artist and name from the image in the format 'Artist Song' without any delimiter. The song is probably located in the upper left but might also be below a square canvas of the song art somewhere in the image. Strip the result from any 'feat.' or 'featuring' or else tag. That is, keep the featured artists names, but remove the 'feat.' tag. If the song name is not visible, just return 'Unknown Song'. If there's no music in the image, return 'No Music'."
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "low"
                        }
                    }
                ]
            }
        ],
        max_tokens=300,
    )

    return response.choices[0].message.content

def create_playlist_and_add_songs(song_info, image_path):
    # Create a new playlist
    playlist_name = "frensrecomms.asia"
    pl_id = spo.find_pl_id(playlist_name, create_missing=True)
    # Search and add single song
    results = spo.search(song_info, type="track", market='FR', limit=5)['tracks']['items']
    if results:
        formatted_results = [f"{' '.join([artist['name'] for artist in track['artists']])} - {track['name']}" for track in results]
        llm_input = [{"query": song_info, "candidates": formatted_results}]

        # LLM prompt
        prompt = f"""Given a song query extracted from image OCR and its search results, determine which result (if any) is the most likely match.
        Since the query comes from OCR, there may be slight errors or inconsistencies in the text.
        Compare the artist name and song title, allowing for minor variations due to OCR errors.
        Return the index (0-4) of the best matching result, or -1 if none of the results are a confident match.
        Be somewhat flexible due to potential OCR errors, but err on the side of caution if no result is clearly similar.

        Input:
        {json.dumps(llm_input, indent=2)}

        Output:
        Only return the matching integer or -1 if no match is found. No text, just the integer."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a music expert helping to match song queries with search results."},
                {"role": "user", "content": prompt}
            ]
        )

        best_index = int(response.choices[0].message.content)
        if best_index == -1:
            # Move the image to the 'not found' folder if no suitable song is found
            shutil.move(image_path, 'not found/')
            print(f"Moved {image_path} to 'not found/' due to no suitable song found")
        else:
            selected_track = results[best_index]
            spo.pl_add_tr(pl_id, selected_track["id"])
            print(f"Added: {song_info} -> {selected_track['artists'][0]['name']} - {selected_track['name']}")
            # Move the image to the 'found' folder if a suitable song is found
            shutil.move(image_path, 'found/')
            print(f"Moved {image_path} to 'found/' after successful addition")

def main():
    image_folder = 'frensrecommsoctnov'
    for image_filename in os.listdir(image_folder):
        image_path = os.path.join(image_folder, image_filename)
        
        # Encode the image to base64
        base64_image = encode_image_to_base64(image_path)
        
        # Extract song information from the image
        song_info = extract_song_info_from_image(base64_image)
        
        # Print the extracted song information
        print(f"Extracted Song Information for {image_filename}:")
        print(song_info)

        # Check if the song information is 'Unknown Song' or 'No Music'
        if song_info == "Unknown Song":
            # Move the image to the 'not found' folder
            shutil.move(image_path, 'not found/')
            print(f"Moved {image_path} to 'not found/' due to 'Unknown Song'")
            continue
        elif song_info == "No Music":
            # Ignore the image
            print(f"Ignored {image_path} due to 'No Music'")
            continue

        # Example usage for Spotify integration
        create_playlist_and_add_songs(song_info, image_path)

if __name__ == "__main__":
    main()