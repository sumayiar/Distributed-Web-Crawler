const photoInput = document.getElementById("photo-input");
const gallery = document.getElementById("gallery");
const verticalScroll = document.getElementById("vertical-scroll");

const seededPhotos = [
  {
    id: "seed-1607",
    name: "IMG_1607.jpg",
    url: "./assets/IMG_1607.jpg",
    caption: "",
  },
  {
    id: "seed-2929",
    name: "IMG_2929.jpg",
    url: "./assets/IMG_2929.jpg",
    caption:
      "These necklaces were trending. I think I got it from Brandy Melville. I had an obsession with the TV show Friends during 9th grade. I went to the famous building! Perk of living in NYC.",
  },
];

let uploadedPhotos = [...seededPhotos];

function renderGallery() {
  gallery.innerHTML = "";

  uploadedPhotos.forEach((photo) => {
    const card = document.createElement("article");
    card.className = "photo-card";

    const image = document.createElement("img");
    image.src = photo.url;
    image.alt = `Uploaded memory: ${photo.name}`;
    image.loading = "lazy";

    const body = document.createElement("div");
    body.className = "photo-card-body";

    const meta = document.createElement("p");
    meta.className = "photo-meta";
    meta.textContent = photo.name;

    const captionInput = document.createElement("textarea");
    captionInput.className = "caption-input";
    captionInput.placeholder = "Write your 2019 memory text for this photo...";
    captionInput.value = photo.caption;
    captionInput.setAttribute("aria-label", `Caption for ${photo.name}`);

    captionInput.addEventListener("input", (event) => {
      photo.caption = event.target.value;
      renderVerticalFeed();
    });

    body.appendChild(meta);
    body.appendChild(captionInput);
    card.appendChild(image);
    card.appendChild(body);
    gallery.appendChild(card);
  });
}

function renderVerticalFeed() {
  verticalScroll.innerHTML = "";

  if (!uploadedPhotos.length) {
    const empty = document.createElement("div");
    empty.className = "feed-empty";
    empty.textContent =
      "Upload photos above and add captions to start your vertical memory scroll.";
    verticalScroll.appendChild(empty);
    return;
  }

  uploadedPhotos.forEach((photo) => {
    const slide = document.createElement("article");
    slide.className = "memory-slide";

    const image = document.createElement("img");
    image.src = photo.url;
    image.alt = `Memory scroll photo: ${photo.name}`;
    image.loading = "lazy";

    const overlay = document.createElement("div");
    overlay.className = "memory-overlay";

    const name = document.createElement("p");
    name.className = "memory-name";
    name.textContent = photo.name;

    const text = document.createElement("p");
    text.className = "memory-text";
    text.textContent =
      photo.caption.trim() || "Add a caption above to pin this memory.";

    overlay.appendChild(name);
    overlay.appendChild(text);
    slide.appendChild(image);
    slide.appendChild(overlay);
    verticalScroll.appendChild(slide);
  });
}

photoInput.addEventListener("change", (event) => {
  const files = Array.from(event.target.files || []);
  const nextPhotos = files.map((file, index) => ({
    id: `${file.name}-${index}`,
    name: file.name,
    url: URL.createObjectURL(file),
    caption: "",
  }));
  uploadedPhotos = [...uploadedPhotos, ...nextPhotos];
  photoInput.value = "";

  renderGallery();
  renderVerticalFeed();
});

renderGallery();
renderVerticalFeed();
