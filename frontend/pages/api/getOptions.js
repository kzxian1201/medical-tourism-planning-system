// frontend/pages/api/getOptions
import path from 'path';
import fs from 'fs/promises';

const getOptionsFromFile = async (fileName, mapFunction) => {
  try {
    const dataDirectory = path.join(process.cwd(), 'ai_service', 'src', 'data');
    const filePath = path.join(dataDirectory, fileName);
    const fileContents = await fs.readFile(filePath, 'utf8');
    const data = JSON.parse(fileContents);
    return mapFunction(data);
  } catch (error) {
    console.error(`Error reading or parsing file: ${fileName}`, error);
    return [];
  }
};

export default async function handler(req, res) {
  const { type } = req.query;
  let options = [];

  try {
    switch (type) {
      case 'medicalPurpose':
        options = await getOptionsFromFile('treatments.json', data =>
          Array.from(new Set(data.map(t => t.name))).map(name => ({ value: name, label: name }))
        );
        break;
      case 'accommodationPreferences':
        options = await getOptionsFromFile('accommodations.json', data =>
          Array.from(
            new Set(
              data.flatMap(country => country.accommodations.flatMap(acc => acc.accessibility_features))
            )
          ).map(f => ({ value: f.toLowerCase().replace(/ /g, '_'), label: f }))
        );
        break;
      default:
        return res.status(400).json({ error: 'Invalid type parameter' });
    }
    res.status(200).json({ options });
  } catch (err) {
    console.error('Error in getOptions API:', err);
    res.status(500).json({ options: [] });
  }
}
