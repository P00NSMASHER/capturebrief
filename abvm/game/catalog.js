(() => {
  const collections = [
    { id:'tops', name:'Tops', icon:'👕', slot:'top', type:'avatar', names:['Comet Hoodie','Garden Tee','Story Cardigan','Colorblock Pullover','Explorer Vest','Star Zip Jacket','Art Smock','Cloud Sweater','Music Crewneck','Trail Shirt'] },
    { id:'bottoms', name:'Bottoms', icon:'👖', slot:'bottom', type:'avatar', names:['Sky Joggers','Berry Skirt','Trail Shorts','Moon Jeans','Garden Overalls','Story Leggings','Comet Cargo Pants','Art Apron Skirt','Cloud Culottes','Explorer Trousers'] },
    { id:'shoes', name:'Shoes', icon:'👟', slot:'shoes', type:'avatar', names:['Star Sneakers','Garden Boots','Cloud Slip-Ons','Trail High-Tops','Story Loafers','Comet Runners','Rainbow Trainers','Art Clogs','Moon Boots','Explorer Hikers'] },
    { id:'headwear', name:'Hair & Headwear', icon:'🎀', slot:'head', type:'avatar', names:['Ribbon Headband','Comet Cap','Garden Crown','Pencil Crown','Orbit Helmet','Story Bow','Cloud Beanie','Trail Visor','Music Headphones','Star Hair Clips'] },
    { id:'glasses', name:'Glasses & Face', icon:'👓', slot:'face', type:'avatar', names:['Gold Star Glasses','Comet Visor','Round Reader Glasses','Rainbow Frames','Garden Specs','Storybook Frames','Moonmark Cheeks','Petal Face Paint','Explorer Stripe','Sparkle Freckles'] },
    { id:'backpacks', name:'Backpacks', icon:'🎒', slot:'back', type:'avatar', names:['Star Backpack','Rocket Backpack','Gear Backpack','Sketchbook Pack','Bubble Buddy Pack','Puzzle Panel Pack','Goo Jar Pack','Bento Buddy Pack','Arcade Pack','Fossil Explorer Pack'] },
    { id:'fidgets', name:'Fun Stuff', icon:'🪄', slot:'hand', type:'avatar', names:['Squeeze-Star Wand','Color Cube Fidget','Infinity Snap Fidget','Foam Ball','Rainbow Mochi','Dino Egg Squishy','Caterpillar Fidget','Book Buddy','Mini Robot Pal','Paint Spinner'] },
    { id:'companions', name:'Friends', icon:'🐾', slot:'companion', type:'companion', names:['Sprout Pup','Moon Cat','Berry Bunny','Sunny Bird','Pebble Turtle','Comet Fox','Story Owl','Bubble Axolotl','Garden Snail','Tiny Robot Friend'] },
    { id:'wall', name:'Room: Walls', icon:'🖼️', slot:'wall', type:'room', names:['Rainbow Poster','Story Map','Garden Garland','Moon Banner','Star Clock','Art Gallery','Music Notes','Comet Mobile','Kindness Pennant','School Star Plaque'] },
    { id:'furniture', name:'Room: Furniture', icon:'🪑', slot:'floor', type:'room', names:['Leafy Plant','Star Lamp','Reading Chair','Art Table','Book Shelf','Cozy Beanbag','Toy Chest','Study Desk','Side Table','Comet Stool'] },
    { id:'bedroom', name:'Room: Bedroom', icon:'🛏️', slot:'bed', type:'room', names:['Cloud Pillow','Rainbow Rug','Star Blanket','Garden Quilt','Storybook Bed','Moon Bed','Comet Bed','Cozy Curtains','Dream Canopy','Galaxy Nightlight'] },
    { id:'magic', name:'Magic Effects', icon:'✨', slot:'aura', type:'avatar', names:['Scholar Sparkle','Cosmic Glow','Garden Glow','Champion Stars','Color Swirl','Storybook Shimmer','Soft Cloud Aura','Aurora Ring','Calm Click Trail','Portal Trail'] },
  ];

  const palettes = [
    ['#6c5ce7','#a29bfe'],['#00a8a8','#63d8d8'],['#ff8c42','#ffc067'],['#e85d75','#ff9bb0'],['#2f80ed','#69a9ff'],
    ['#35a853','#83d69a'],['#8d6e63','#c6a28f'],['#7b61ff','#c0b5ff'],['#e1a500','#ffd55d'],['#3d405b','#7a819f']
  ];

  const items = [];
  collections.forEach((collection, cIndex) => {
    collection.names.forEach((name, i) => {
      const priceTickets = i < 5 ? 3 : i < 8 ? 6 : 9;
      const [primary, secondary] = palettes[(i + cIndex * 2) % palettes.length];
      items.push({
        id:`${collection.id}-${i+1}`,
        collectionId:collection.id,
        collectionName:collection.name,
        collectionIcon:collection.icon,
        slot:collection.slot,
        type:collection.type,
        name,
        index:i,
        styleKey:`${collection.id}-${i}`,
        priceTickets,
        priceCoins:priceTickets * 20,
        primary,
        secondary,
      });
    });
  });

  window.ABVM_CATALOG = { collections, items };
})();
