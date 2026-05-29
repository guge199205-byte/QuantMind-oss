declare module 'antd/es/tag' {
  interface TagProps {
    size?: 'small' | 'middle' | 'large' | string;
  }
}

// Keep module augmentation minimal to avoid overwriting 'antd' declarations
  export { }
